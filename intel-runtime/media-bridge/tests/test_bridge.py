from __future__ import annotations

import asyncio
import contextlib
from dataclasses import replace
import io
import json
import os
from pathlib import Path
import socket
import sys
import tempfile
import time
import unittest
from unittest.mock import patch

from PIL import Image
from websockets.asyncio.server import serve

from morph_media_bridge.__main__ import InstanceLock, preflight
from morph_media_bridge.config import Config, ConfigError, private_token
from morph_media_bridge.frames import LatestFrame, Stats, advance_deadline, synthetic_jpeg, valid_jpeg
from morph_media_bridge.http_status import StatusServer
from morph_media_bridge.publisher import FFmpegPublisher, ffmpeg_command, publish_latest
from morph_media_bridge.source import receive_studio, receive_synthetic
from tools.prepare_synthetic import prepare


ROOT = Path(__file__).resolve().parents[1]
TEST_TOKEN = "local-fixture-token-for-offline-tests-only"


def raw_config() -> dict:
    data = json.loads((ROOT / "examples/synthetic.json").read_text())
    data["profile"] = {"width": 128, "height": 96, "fps": 30}
    data["status"]["tokenFile"] = "status.token"
    data["runtimeDir"] = "bridge"
    data["limits"].update(writeTimeoutMs=25, maxReceiptAgeMs=100, reconnectMinMs=25, reconnectMaxMs=100)
    return data


class Fixture:
    def setup_fixture(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name)
        self.token_file = self.base / "status.token"
        self.token_file.write_text(TEST_TOKEN)
        self.token_file.chmod(0o600)
        self.config = Config.parse(raw_config(), self.base)


class ConfigTests(Fixture, unittest.TestCase):
    def setUp(self):
        self.setup_fixture()

    def test_explicit_simulation_and_safe_urls(self):
        self.assertEqual(self.config.source_mode, "simulation")
        self.assertEqual(self.config.encoder, "libx264")
        edits = [lambda x: x.update(sourceMode="live"), lambda x: x.update(inputMode="auto"),
                 lambda x: x["publisher"].update(rtspUrl="rtsp://other-host:8554/inspection"),
                 lambda x: x["publisher"].update(rtspUrl="rtsp://user:secret@127.0.0.1:8554/inspection"),
                 lambda x: x["publisher"].update(rtspUrl="rtsp://127.0.0.1:8554/other"),
                 lambda x: x["publisher"].update(encoder="h264_qsv"),
                 lambda x: x["publisher"].update(bitrateKbps=0),
                 lambda x: x["status"].update(host="0.0.0.0"), lambda x: x["profile"].update(width=127),
                 lambda x: x.update(unrecognized=True), lambda x: x["limits"].update(maxJpegBytes=999999999)]
        for edit in edits:
            with self.subTest(edit=edit):
                data = raw_config()
                edit(data)
                with self.assertRaises(ConfigError):
                    Config.parse(data, self.base)

    def test_studio_camera_is_exact_and_required(self):
        data = raw_config()
        data.update(inputMode="studio", sourceMode="live")
        data["studio"] = {"baseUrl": "ws://127.0.0.1:3000", "camera": {
            "name": "fixture", "hardware_name": "fixture", "driver": "fixture-driver",
            "fingerprint": {"id": "synthetic-only"}, "payload": {"width": 128, "height": 96, "fps": 30}}}
        config = Config.parse(data, self.base)
        from urllib.parse import parse_qs, urlsplit
        received = json.loads(parse_qs(urlsplit(config.studio_url).query)["camera"][0])
        self.assertEqual(received, data["studio"]["camera"])
        for field, value in (("fingerprint", {}), ("payload", {"width": 640, "height": 480, "fps": 30})):
            altered = json.loads(json.dumps(data))
            altered["studio"]["camera"][field] = value
            with self.assertRaises(ConfigError):
                Config.parse(altered, self.base)
        data["studio"]["baseUrl"] = "ws://other-host:3000"
        with self.assertRaises(ConfigError):
            Config.parse(data, self.base)

    def test_private_file_permissions_and_symlink(self):
        self.assertEqual(private_token(self.token_file), TEST_TOKEN)
        self.token_file.chmod(0o644)
        with self.assertRaises(ConfigError):
            private_token(self.token_file)
        self.token_file.chmod(0o600)
        alias = self.base / "alias"
        alias.symlink_to(self.token_file)
        with self.assertRaises(ConfigError):
            private_token(alias)
        self.token_file.write_text("short")
        with self.assertRaises(ConfigError):
            private_token(self.token_file)

    def test_runtime_lock_prevents_second_owner(self):
        with InstanceLock(self.config.runtime_dir):
            with self.assertRaises(ConfigError):
                with InstanceLock(self.config.runtime_dir):
                    pass
        with InstanceLock(self.config.runtime_dir):
            pass

    def test_synthetic_generator_keeps_secrets_private_and_disables_other_protocols(self):
        directory = self.base / "generated"
        result = prepare(directory, "ffmpeg")
        self.assertEqual(directory.stat().st_mode & 0o777, 0o700)
        for name in ("status.token", "viewer-password.token", "bridge.json", "mediamtx.yml"):
            self.assertEqual((directory / name).stat().st_mode & 0o777, 0o600)
        self.assertEqual(Config.load(directory / "bridge.json").source_mode, "simulation")
        status = private_token(directory / "status.token")
        viewer = private_token(directory / "viewer-password.token")
        self.assertNotEqual(status, viewer)
        self.assertNotIn(status, json.dumps(result))
        self.assertNotIn(viewer, json.dumps(result))
        media = (directory / "mediamtx.yml").read_text()
        self.assertIn("moq: false", media)
        self.assertIn("rtspAddress: 127.0.0.1:8554", media)
        self.assertIn("overridePublisher: false", media)
        self.assertNotIn("REPLACE_WITH_PRIVATE_GENERATED_PASSWORD", media)
        with self.assertRaises(FileExistsError):
            prepare(directory)

    def test_studio_example_cannot_open_a_default_camera(self):
        with self.assertRaises(ConfigError):
            Config.load(ROOT / "examples/studio.json")

    def test_command_has_explicit_encoder_no_shell_or_fallback(self):
        args = ffmpeg_command(self.config)
        for left, right in (("-tune", "zerolatency"), ("-profile:v", "baseline"), ("-bf", "0"),
                            ("-preset", "ultrafast"), ("-rtsp_transport", "tcp")):
            self.assertEqual(args[args.index(left) + 1], right)
        self.assertEqual(args[-1], "rtsp://127.0.0.1:8554/inspection")
        self.assertNotIn("h264_qsv", args)
        self.assertEqual(args[args.index("-maxrate") + 1], "1500k")
        self.assertEqual(args[args.index("-bufsize") + 1], "300k")
        self.assertEqual(args[args.index("-use_wallclock_as_timestamps") + 1], "1")
        self.assertEqual(args[args.index("-framerate") + 1], str(self.config.fps))
        self.assertEqual(args[args.index("-enc_time_base:v") + 1], "1:90000")
        self.assertIn("PREV_OUTPTS+1", args[args.index("-vf") + 1])

    def test_bitrate_is_configurable_and_default_is_explicit(self):
        data = raw_config()
        data["publisher"]["bitrateKbps"] = 1200
        config = Config.parse(data, self.base)
        command = ffmpeg_command(config)
        self.assertEqual(command[command.index("-maxrate") + 1], "1200k")
        self.assertEqual(command[command.index("-bufsize") + 1], "240k")
        del data["publisher"]["bitrateKbps"]
        self.assertEqual(Config.parse(data, self.base).bitrate_kbps, 1500)


class FrameTests(Fixture, unittest.TestCase):
    def setUp(self):
        self.setup_fixture()
        self.stats = Stats(self.config)

    def test_latest_slot_replaces_without_queue(self):
        slot = LatestFrame(self.stats)
        for i in range(200):
            slot.offer(bytes([i]), now=10)
        self.assertEqual(slot.take().jpeg, bytes([199]))
        self.assertIsNone(slot.take())
        self.assertEqual(self.stats.counters["replacedFrames"], 199)
        self.assertEqual(self.stats.pending_bytes, 0)

    def test_cadence_does_not_add_work_time_or_queue_missed_ticks(self):
        next_due, skipped = advance_deadline(10, 0.1, 10.025)
        self.assertAlmostEqual(next_due, 10.1)
        self.assertEqual(skipped, 0)
        next_due, skipped = advance_deadline(10, 0.1, 10.35)
        self.assertAlmostEqual(next_due, 10.4)
        self.assertEqual(skipped, 3)

    def test_jpeg_validation_does_not_decode_superseded_frames(self):
        jpeg = synthetic_jpeg(128, 96, 1)
        with patch.object(Image.Image, "load", side_effect=AssertionError("pixel decode forbidden")):
            self.assertTrue(valid_jpeg(jpeg, self.config, self.stats))

    def test_invalid_oversized_wrong_profile_and_truncated_rejected(self):
        valid = synthetic_jpeg(128, 96, 1)
        for data in ("text", b"not-jpeg", valid[:-2], synthetic_jpeg(64, 64, 2)):
            self.assertFalse(valid_jpeg(data, self.config, self.stats))
        self.assertFalse(valid_jpeg(b"x" * (self.config.max_jpeg_bytes + 1), self.config, self.stats))
        self.assertEqual(self.stats.counters["invalidFrames"], 4)
        self.assertEqual(self.stats.counters["oversizedFrames"], 1)

    def test_synthetic_changes_visible_pixels(self):
        first, second = synthetic_jpeg(128, 96, 1), synthetic_jpeg(128, 96, 2)
        self.assertNotEqual(first, second)
        with Image.open(io.BytesIO(first)) as a, Image.open(io.BytesIO(second)) as b:
            self.assertNotEqual(a.tobytes(), b.tobytes())

    def test_receipt_age_never_claims_capture_latency(self):
        slot = LatestFrame(self.stats)
        slot.offer(b"fixture", now=10)
        self.stats.source_state, self.stats.publisher_state = "connected", "streaming"
        status = self.stats.status(now=10.05)
        self.assertEqual(status["receiptAgeMs"], 50)
        self.assertFalse(status["captureTimestampAvailable"])
        self.assertNotIn("captureLatencyMs", status)
        self.assertEqual(status["sourceMode"], "simulation")
        self.assertEqual(self.stats.status(now=11)["state"], "stale")
        self.assertNotIn(TEST_TOKEN, json.dumps(status))


class AsyncTests(Fixture, unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.setup_fixture()
        self.stats, self.stop = Stats(self.config), asyncio.Event()
        self.slot = LatestFrame(self.stats)

    async def cancel(self, task):
        self.stop.set()
        task.cancel()
        await asyncio.wait_for(asyncio.gather(task, return_exceptions=True), 2)

    async def test_slow_writer_is_bounded_and_closes_on_cancel(self):
        entered, closed = asyncio.Event(), asyncio.Event()
        class Slow:
            async def start(self):
                pass
            async def write(self, data):
                entered.set()
                await asyncio.Event().wait()
            async def close(self):
                closed.set()
        config = replace(self.config, write_timeout_ms=1000, max_receipt_age_ms=2000)
        task = asyncio.create_task(publish_latest(config, self.slot, self.stats, self.stop, lambda *_: Slow()))
        self.slot.offer(b"initial")
        await asyncio.wait_for(entered.wait(), 1)
        for i in range(1000):
            self.slot.offer(b"latest")
        self.assertEqual(self.stats.inflight_bytes, len(b"initial"))
        self.assertEqual(self.stats.pending_bytes, len(b"latest"))
        self.assertEqual(self.stats.counters["replacedFrames"], 999)
        await self.cancel(task)
        self.assertTrue(closed.is_set())
        self.assertEqual(self.stats.inflight_bytes, 0)

    async def test_write_timeout_restarts_and_discards_partial(self):
        created, closed = [], []
        class Slow:
            async def start(inner):
                created.append(inner)
            async def write(inner, data):
                await asyncio.Event().wait()
            async def close(inner):
                closed.append(inner)
        task = asyncio.create_task(publish_latest(self.config, self.slot, self.stats, self.stop, lambda *_: Slow()))
        self.slot.offer(b"frame")
        await asyncio.sleep(0.12)
        await self.cancel(task)
        self.assertEqual(self.stats.counters["writeTimeouts"], 1)
        self.assertEqual(self.stats.counters["submittedFrames"], 0)
        self.assertGreaterEqual(len(created), 2)
        self.assertEqual(len(closed), len(created))

    async def test_stale_frame_never_reaches_writer(self):
        written = []
        class Writer:
            async def start(inner):
                pass
            async def write(inner, data):
                written.append(data)
            async def close(inner):
                pass
        self.slot.offer(b"old", now=time.monotonic() - 2)
        task = asyncio.create_task(publish_latest(self.config, self.slot, self.stats, self.stop, lambda *_: Writer()))
        await asyncio.sleep(0.03)
        self.slot.offer(b"fresh")
        await asyncio.sleep(0.03)
        await self.cancel(task)
        self.assertEqual(written, [b"fresh"])
        self.assertEqual(self.stats.counters["staleFrames"], 1)
        self.assertEqual(self.stats.counters["submittedFrames"], 1)

    async def test_backoff_is_bounded_and_cancel_interrupts(self):
        calls = []
        class Unavailable:
            async def __aenter__(inner):
                calls.append(time.monotonic())
                raise OSError("fixture")
            async def __aexit__(inner, *args):
                pass
        task = asyncio.create_task(receive_studio(self.config, self.slot, self.stats, self.stop, lambda *a, **k: Unavailable()))
        await asyncio.sleep(0.2)
        started = time.monotonic()
        await self.cancel(task)
        self.assertLess(time.monotonic() - started, 0.2)
        self.assertGreaterEqual(len(calls), 3)
        self.assertLessEqual(len(calls), 4)
        self.assertGreaterEqual(calls[1] - calls[0], 0.02)
        self.assertGreaterEqual(calls[2] - calls[1], 0.04)

    async def test_real_local_websocket_reconnect_and_single_subscription(self):
        active = maximum = connections = 0
        got_two = asyncio.Event()
        async def handler(ws):
            nonlocal active, maximum, connections
            active += 1
            connections += 1
            maximum = max(maximum, active)
            try:
                await ws.send("invalid fixture metadata")
                await ws.send(synthetic_jpeg(128, 96, connections))
                if connections == 1:
                    await ws.close()
                else:
                    got_two.set()
                    await ws.wait_closed()
            finally:
                active -= 1
        async with serve(handler, "127.0.0.1", 0) as server:
            port = server.sockets[0].getsockname()[1]
            config = replace(self.config, studio_url=f"ws://127.0.0.1:{port}/api/cameras/ws")
            task = asyncio.create_task(receive_studio(config, self.slot, self.stats, self.stop))
            await asyncio.wait_for(got_two.wait(), 2)
            await asyncio.sleep(0.02)
            await self.cancel(task)
        self.assertEqual(maximum, 1)
        self.assertEqual(connections, 2)
        self.assertEqual(self.stats.counters["acceptedFrames"], 2)
        self.assertEqual(self.stats.counters["invalidFrames"], 2)
        self.assertGreaterEqual(self.stats.counters["sourceReconnects"], 1)
        self.assertIsNone(self.slot.frame)

    async def test_websocket_oversize_closes_then_reconnects(self):
        connected = asyncio.Event()
        async def handler(ws):
            await ws.send(b"x" * 5000)
            connected.set()
            await ws.wait_closed()
        async with serve(handler, "127.0.0.1", 0) as server:
            port = server.sockets[0].getsockname()[1]
            config = replace(self.config, max_jpeg_bytes=4096, studio_url=f"ws://127.0.0.1:{port}")
            task = asyncio.create_task(receive_studio(config, self.slot, self.stats, self.stop))
            await asyncio.wait_for(connected.wait(), 1)
            await asyncio.sleep(0.02)
            await self.cancel(task)
        self.assertGreaterEqual(self.stats.counters["oversizedFrames"], 1)
        self.assertEqual(self.stats.counters["acceptedFrames"], 0)

    async def test_source_stall_is_counted_and_subscription_is_closed(self):
        disconnected = asyncio.Event()
        async def handler(ws):
            await ws.wait_closed()
            disconnected.set()
        async with serve(handler, "127.0.0.1", 0) as server:
            port = server.sockets[0].getsockname()[1]
            config = replace(self.config, source_timeout_ms=100, studio_url=f"ws://127.0.0.1:{port}")
            task = asyncio.create_task(receive_studio(config, self.slot, self.stats, self.stop))
            await asyncio.wait_for(disconnected.wait(), 1)
            await self.cancel(task)
        self.assertEqual(self.stats.counters["sourceTimeouts"], 1)
        self.assertEqual(self.stats.last_error, "source-timeout")
        self.assertEqual(self.stats.source_state, "disconnected")

    async def test_synthetic_source_is_labeled_and_cancellable(self):
        task = asyncio.create_task(receive_synthetic(self.config, self.slot, self.stats, self.stop))
        await asyncio.sleep(0.09)
        self.assertGreaterEqual(self.stats.counters["acceptedFrames"], 2)
        self.assertEqual(self.stats.status()["sourceMode"], "simulation")
        await self.cancel(task)
        self.assertEqual(self.stats.source_state, "disconnected")

    async def test_http_auth_liveness_read_only_and_sanitized(self):
        # Port zero is test-only; production configuration requires explicit 1..65535.
        config = replace(self.config, status_port=0)
        server = StatusServer(config, self.stats)
        await server.start()
        port = server.server.sockets[0].getsockname()[1]
        async def request(path, token=None, method="GET"):
            reader, writer = await asyncio.open_connection("127.0.0.1", port)
            auth = "" if token is None else f"Authorization: Bearer {token}\r\n"
            writer.write(f"{method} {path} HTTP/1.1\r\nHost: localhost\r\n{auth}\r\n".encode())
            await writer.drain()
            data = await reader.read()
            writer.close()
            await writer.wait_closed()
            return data
        try:
            self.assertIn(b" 200 ", await request("/health"))
            self.assertIn(b" 401 ", await request("/api/media/v1/status"))
            self.assertIn(b" 401 ", await request("/api/media/v1/status", "wrong"))
            self.assertIn(b" 405 ", await request("/api/media/v1/status", TEST_TOKEN, "POST"))
            valid = await request("/api/media/v1/status", TEST_TOKEN)
            self.assertIn(b" 200 ", valid)
            self.assertIn(b'"sourceMode":"simulation"', valid)
            self.assertNotIn(TEST_TOKEN.encode(), valid)
            self.assertNotIn(b"rtsp", valid)
            self.assertIn(b" 404 ", await request("/api/media/v1/status?token=anything", TEST_TOKEN))
        finally:
            await server.close()

    async def test_owned_encoder_process_group_closes(self):
        publisher = FFmpegPublisher(self.config, self.stats)
        with patch("morph_media_bridge.publisher.ffmpeg_command", return_value=[sys.executable, "-c", "import time; time.sleep(60)"]):
            await publisher.start()
        pid = publisher.process.pid
        self.assertEqual(os.getpgid(pid), pid)
        await publisher.close()
        with self.assertRaises(ProcessLookupError):
            os.kill(pid, 0)
        self.assertIsNone(publisher.process)

    async def test_cancel_during_encoder_creation_still_closes_child(self):
        publisher = FFmpegPublisher(self.config, self.stats)
        created = asyncio.Event()
        owned = []
        real_create = asyncio.create_subprocess_exec
        async def delayed_create(*args, **kwargs):
            process = await real_create(sys.executable, "-c", "import time; time.sleep(60)", **kwargs)
            owned.append(process)
            created.set()
            await asyncio.sleep(0.03)
            return process
        with patch("morph_media_bridge.publisher.asyncio.create_subprocess_exec", side_effect=delayed_create):
            task = asyncio.create_task(publisher.start())
            await asyncio.wait_for(created.wait(), 1)
            task.cancel()
            await asyncio.gather(task, return_exceptions=True)
        self.assertIsNotNone(owned[0].returncode)
        self.assertIsNone(publisher.process)


if __name__ == "__main__":
    unittest.main()

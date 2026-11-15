"""Offline contract, secret handling, and owned process lifecycle regressions."""
from __future__ import annotations

from contextlib import contextmanager
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
from pathlib import Path
import signal
import socket
import subprocess
import sys
import tempfile
import threading
import time
import unittest
from unittest.mock import patch

TOOLS = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(TOOLS))
import check_station as checker
import run_station as launcher


def fixtures(empty=False):
    metrics = {"finishedCycles": 0}
    session = None if empty else {"id": "test-session", "sourceMode": "simulation"}
    snapshot = {"generatedAt": "2026-11-15T10:00:00Z", "lastEventSequence": 1, "metrics": metrics,
                "session": session, "sourceMode": None if empty else "simulation", "cycle": None}
    return {
        "/api/local/v1/runtime": {"version": 1, "runtimeMode": "demo", "recordsTransport": "local-simulation", "stationId": None, "controlHost": "jose", "motionRoutes": False},
        "/api/v1/schema": {"capabilities": {"dashboardRead": {"version": 1, "path": "/api/v1/dashboard"}}},
        "/api/v1/dashboard?sourceMode=simulation&limit=1": {"schemaVersion": 1, "dashboardVersion": 1, **snapshot, "sourceMode": "simulation",
            "snapshot": snapshot, "selectedSessionId": None if empty else "test-session", "metrics": metrics,
            "sessions": {"items": [] if empty else [dict(session)], "limit": 50, "total": 0 if empty else 1},
            "recentCycles": {"items": [], "limit": 1, "offset": 0, "total": 0}, "currentDetail": None, "detail": None},
        "/api/media/v1/status": {"version": 1, "configured": False, "sourceMode": "simulation", "producer": None}}


@contextmanager
def server(routes):
    requests = []
    class Handler(BaseHTTPRequestHandler):
        protocol_version = "HTTP/1.1"
        def do_GET(self):
            requests.append((self.command, self.path))
            value = routes.get(self.path, (404, {"private": "remote-secret-must-not-appear"}))
            status, body = value if isinstance(value, tuple) else (200, value)
            payload = json.dumps(body).encode()
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(payload)))
            self.send_header("Connection", "close")
            self.end_headers()
            self.wfile.write(payload)
        def log_message(self, *args):
            pass
    httpd = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    try:
        yield httpd.server_port, requests
    finally:
        httpd.shutdown()
        httpd.server_close()
        thread.join()


class ReadinessTests(unittest.TestCase):
    def test_four_gets_empty_data_is_independent_from_media(self):
        with server(fixtures(empty=True)) as (port, requests):
            result = checker.check(port, "simulation", timeout=2)
        self.assertTrue(result["ok"])
        self.assertEqual(result["records"]["eligibleData"], "no-eligible-session")
        self.assertFalse(result["media"]["configured"])
        self.assertEqual(len(requests), 4)
        self.assertTrue(all(method == "GET" for method, _ in requests))
        self.assertEqual({path for _, path in requests}, set(fixtures()))
        self.assertNotIn("hardwareReady", result)

    def test_remote_error_and_ice_credentials_are_not_echoed(self):
        data = fixtures()
        data["/api/v1/schema"] = (503, {"detail": "remote-secret-must-not-appear"})
        data["/api/media/v1/status"].update({"reason": "remote-secret-must-not-appear", "iceServers": [{"credential": "remote-secret-must-not-appear"}]})
        with server(data) as (port, _):
            result = checker.check(port, "simulation", timeout=2)
        self.assertFalse(result["ok"])
        self.assertEqual(result["schema"], {"status": "http-error", "httpStatus": 503})
        self.assertNotIn("remote-secret", json.dumps(result))

    def test_no_redirect_following_and_size_bound(self):
        with server({"/redirect": (302, {}), "/large": {"data": "x" * 2048}}) as (port, requests):
            self.assertEqual(checker.get_json(port, "/redirect")["httpStatus"], 302)
            self.assertEqual(checker.get_json(port, "/large", max_bytes=1024)["status"], "oversized-response")
        self.assertEqual(len(requests), 2)

    def test_absolute_deadline_interrupts_dripping_headers(self):
        with socket.socket() as listener:
            listener.bind(("127.0.0.1", 0))
            listener.listen()
            stop = threading.Event()
            def drip():
                connection, _ = listener.accept()
                with connection:
                    connection.recv(4096)
                    try:
                        connection.sendall(b"HTTP/1.1 200 OK\r\nX-Slow: ")
                        while not stop.wait(0.05):
                            connection.sendall(b"x")
                    except OSError:
                        pass
            thread = threading.Thread(target=drip, daemon=True)
            thread.start()
            started = time.monotonic()
            result = checker.get_json(listener.getsockname()[1], "/", timeout=0.25)
            stop.set()
            thread.join(timeout=2)
        self.assertLess(time.monotonic() - started, 1.5)
        self.assertNotEqual(result["status"], "ok")

    def test_invalid_shapes_do_not_leak_or_crash(self):
        self.assertEqual(checker.summarize_schema({"status": "ok", "data": {"capabilities": []}})["dashboardRead"], "unavailable")
        data = {"version": 1, "configured": True, "sourceMode": "simulation", "producer": {"state": {"secret": "hidden"}}}
        self.assertEqual(checker.summarize_media({"status": "ok", "data": data}, "simulation")["producerStatus"], "unavailable")

    def test_mismatched_snapshot_is_rejected(self):
        data = fixtures()["/api/v1/dashboard?sourceMode=simulation&limit=1"]
        data["snapshot"] = {**data["snapshot"], "lastEventSequence": 0}
        self.assertEqual(checker.summarize_records({"status": "ok", "data": data}, "simulation"), {"status": "invalid-contract"})

    def test_selected_session_and_source_are_checked_at_each_contract_level(self):
        def populated():
            data = fixtures()["/api/v1/dashboard?sourceMode=simulation&limit=1"]
            cycle = {"id": "cycle-1", "sessionId": "test-session"}
            data["snapshot"]["cycle"] = dict(cycle)
            data["recentCycles"].update({"items": [dict(cycle)], "total": 1})
            data["currentDetail"] = {"cycle": dict(cycle), "frames": [{"sessionId": "test-session", "cycleId": "cycle-1"}]}
            data["detail"] = {"cycle": dict(cycle)}
            return data
        valid = populated()
        self.assertEqual(checker.summarize_records({"status": "ok", "data": valid}, "simulation")["status"], "ok")
        mutations = (
            lambda d: d["snapshot"]["session"].update(id="other-session"),
            lambda d: d["snapshot"]["session"].update(sourceMode="live"),
            lambda d: d["snapshot"].update(sourceMode="live"),
            lambda d: d["sessions"]["items"][0].update(sourceMode="live"),
            lambda d: d["recentCycles"]["items"][0].update(sessionId="other-session"),
            lambda d: d["recentCycles"]["items"][0].update(sourceMode="live"),
            lambda d: d["snapshot"]["cycle"].update(sessionId="other-session"),
            lambda d: d["currentDetail"]["cycle"].update(id="other-cycle"),
            lambda d: d["detail"]["cycle"].update(sessionId="other-session"),
            lambda d: d["currentDetail"]["frames"][0].update(cycleId="other-cycle"),
            lambda d: d["currentDetail"]["frames"][0].update(sourceMode="live"),
        )
        for index, mutate in enumerate(mutations):
            with self.subTest(case=index):
                data = populated()
                mutate(data)
                self.assertEqual(checker.summarize_records({"status": "ok", "data": data}, "simulation")["status"], "invalid-contract")

    def test_no_selected_session_cannot_hide_a_populated_snapshot(self):
        data = fixtures(empty=True)["/api/v1/dashboard?sourceMode=simulation&limit=1"]
        data["snapshot"]["session"] = {"id": "hidden-session", "sourceMode": "simulation"}
        self.assertEqual(checker.summarize_records({"status": "ok", "data": data}, "simulation")["status"], "invalid-contract")

    def test_missing_selection_field_is_invalid_instead_of_crashing(self):
        data = fixtures(empty=True)["/api/v1/dashboard?sourceMode=simulation&limit=1"]
        del data["selectedSessionId"]
        self.assertEqual(checker.summarize_records({"status": "ok", "data": data}, "simulation")["status"], "invalid-contract")

    def test_media_required_is_explicit_and_source_mode_matters(self):
        data = fixtures()
        data["/api/media/v1/status"].update({"configured": True, "sourceMode": "live", "producer": {"state": "streaming", "receiptAgeMs": 2.5, "counters": {"encodedFramesReported": 10}}})
        with server(data) as (port, _):
            result = checker.check(port, "simulation", timeout=2, require_media=True)
        self.assertFalse(result["ok"])
        self.assertEqual(result["media"]["producerReceiptAgeMs"], 2.5)
        self.assertEqual(result["media"]["captureLatency"], "not-measured")


class LauncherTests(unittest.TestCase):
    def test_environment_drops_inherited_credentials_and_runtime_options(self):
        with patch.dict(os.environ, {"MORPH_CONTEXT_PAIRING_DIR": "secret", "OPENAI_API_KEY": "secret", "NODE_OPTIONS": "secret", "PYTHONPATH": "secret", "HTTP_PROXY": "secret", "MORPH_MEDIA_CONFIG_FILE": "secret"}):
            env = launcher.environment("/prepared/node")
        self.assertTrue(set(env) <= {"PATH", "LANG", "LC_ALL", "TMPDIR"})
        self.assertNotIn("secret", json.dumps(env))

    def test_occupied_port_never_replaces_listener(self):
        with socket.socket() as listener:
            listener.bind(("127.0.0.1", 0))
            listener.listen()
            port = listener.getsockname()[1]
            reservation = launcher.Reservations()
            with self.assertRaises(launcher.LaunchError):
                reservation.reserve("dashboard", port)
            with socket.create_connection(("127.0.0.1", port), timeout=1):
                pass

    def test_private_configuration_rejects_public_file_and_symlink(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "configuration"
            path.write_text("private-value")
            path.chmod(0o644)
            with self.assertRaises(launcher.LaunchError):
                launcher.private_path(path, directory=False)
            path.chmod(0o600)
            self.assertEqual(launcher.private_path(path, directory=False), path.resolve())
            link = Path(directory) / "link"
            link.symlink_to(path)
            with self.assertRaises(launcher.LaunchError):
                launcher.private_path(link, directory=False)

    def test_recently_closed_tcp_listener_can_restart_without_adopting_a_process(self):
        with socket.socket() as listener:
            listener.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            listener.bind(("127.0.0.1", 0))
            listener.listen()
            port = listener.getsockname()[1]
            with socket.create_connection(("127.0.0.1", port), timeout=1) as client:
                connection, _ = listener.accept()
                connection.close()
                self.assertEqual(client.recv(1), b"")
        reservations = launcher.Reservations()
        try:
            self.assertEqual(reservations.reserve("dashboard", port), port)
        finally:
            reservations.close()

    def test_generated_topology_has_private_credentials_and_dynamic_ports(self):
        with tempfile.TemporaryDirectory() as directory:
            runtime = Path(directory) / "media"
            ports = {"rtsp": 18554, "whep": 18889, "status": 18790, "ice": 18189}
            gateway_path = launcher.prepare_media(runtime, sys.executable, ports, 30)
            gateway = json.loads(gateway_path.read_text())
            bridge = json.loads((runtime / "bridge.json").read_text())
            self.assertEqual(bridge["inputMode"], "synthetic")
            self.assertEqual(bridge["sourceMode"], "simulation")
            self.assertEqual(bridge["profile"]["fps"], 30)
            self.assertIn(":18554/", bridge["publisher"]["rtspUrl"])
            self.assertIn(":18889/", gateway["whepUrl"])
            self.assertEqual(gateway_path.stat().st_mode & 0o777, 0o600)
            media = (runtime / "mediamtx.yml").read_text()
            self.assertIn("moq: false", media)
            self.assertIn("webrtcLocalUDPAddress: 127.0.0.1:18189", media)

    def test_failed_child_cleans_sibling_without_exposing_output(self):
        supervisor = launcher.Supervisor()
        try:
            sibling = supervisor.spawn("sibling", [sys.executable, "-c", "import time; time.sleep(60)"], cwd=TOOLS, env={})
            failed = supervisor.spawn("failed", [sys.executable, "-c", "print('private-diagnostic'); raise SystemExit(3)"], cwd=TOOLS, env={})
            failed.process.wait(timeout=3)
            with self.assertRaisesRegex(launcher.LaunchError, "Owned failed process exited"):
                supervisor.healthy()
        finally:
            report = supervisor.close(grace=0.2)
        self.assertIsNotNone(sibling.process.poll())
        self.assertTrue(report["ownedProcessesStopped"])
        self.assertNotIn("private-diagnostic", json.dumps(report))

    def test_ctrl_c_cleans_nested_new_session_but_preserves_unrelated_process(self):
        with tempfile.TemporaryDirectory() as directory:
            runtime = Path(directory)
            helper = runtime / "helper.py"
            report_path = runtime / "result.json"
            ready = runtime / "ready"
            helper.write_text("import sys,signal,time,json\nfrom pathlib import Path\n"
                f"sys.path.insert(0,{str(TOOLS)!r})\nfrom run_station import Supervisor\ns=Supervisor()\n"
                "signal.signal(signal.SIGINT,lambda *_:setattr(s,'stopping',True))\n"
                f"nested={('import signal,time; signal.signal(signal.SIGTERM,signal.SIG_IGN); time.sleep(60)')!r}\n"
                "parent='import signal,subprocess,sys,time; signal.signal(signal.SIGTERM,signal.SIG_IGN); subprocess.Popen([sys.executable,\"-c\",'+repr(nested)+'],start_new_session=True); time.sleep(60)'\n"
                f"s.spawn('nested',[sys.executable,'-c',parent],cwd=Path({str(runtime)!r}),env={{}})\n"
                "end=time.monotonic()+2\nwhile time.monotonic()<end:\n s.observe(); time.sleep(.02)\n"
                f"Path({str(ready)!r}).write_text('ready')\n"
                "while not s.stopping: s.observe(); time.sleep(.02)\n"
                f"Path({str(report_path)!r}).write_text(json.dumps(s.close(grace=.15)))\n")
            sentinel = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(60)"], start_new_session=True)
            worker = subprocess.Popen([sys.executable, str(helper)], stdout=subprocess.PIPE, stderr=subprocess.PIPE, start_new_session=True)
            try:
                deadline = time.monotonic() + 5
                while not ready.exists() and time.monotonic() < deadline:
                    self.assertIsNone(worker.poll())
                    time.sleep(0.05)
                self.assertTrue(ready.exists())
                worker.send_signal(signal.SIGINT)
                output, errors = worker.communicate(timeout=8)
                self.assertEqual(worker.returncode, 0, errors.decode())
                report = json.loads(report_path.read_text())
                self.assertTrue(report["ownedProcessesStopped"])
                self.assertGreaterEqual(report["observedOwnedProcessCount"], 2)
                self.assertIsNone(sentinel.poll())
            finally:
                if worker.poll() is None:
                    os.killpg(worker.pid, signal.SIGKILL)
                    worker.wait()
                os.killpg(sentinel.pid, signal.SIGTERM)
                sentinel.wait(timeout=3)


if __name__ == "__main__":
    unittest.main()

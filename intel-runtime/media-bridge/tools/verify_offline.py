#!/usr/bin/env python3
"""Local synthetic regression and optional real software-encoder verification."""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import importlib.metadata
import io
import json
import os
from pathlib import Path
import platform
import shutil
import subprocess
import sys
import tempfile
import time
import unittest


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from morph_media_bridge.config import Config
from morph_media_bridge.frames import synthetic_jpeg
from morph_media_bridge.publisher import ffmpeg_command


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--ffmpeg", default="ffmpeg")
    parser.add_argument("--ffprobe", default="ffprobe")
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=False)
    log = io.StringIO()
    suite = unittest.defaultTestLoader.discover(str(ROOT / "tests"))
    result = unittest.TextTestRunner(stream=log, verbosity=2).run(suite)
    (args.output / "tests.log").write_text(log.getvalue())
    encoder = {"attempted": False, "verified": False}
    if shutil.which(args.ffmpeg) and shutil.which(args.ffprobe):
        with tempfile.TemporaryDirectory(prefix="morph-media-encoder-") as temporary:
            base = Path(temporary)
            data = json.loads((ROOT / "examples/synthetic.json").read_text())
            data["publisher"]["ffmpeg"] = args.ffmpeg
            config = Config.parse(data, base)
            path = base / "synthetic.nut"
            # Preserve packet timestamps in a local container. A deliberate input pause
            # verifies that dropped/missing frames do not compress the output timeline.
            command = ffmpeg_command(config, validation_output=str(path))
            # NUT preserves the fine encoder time base. Matroska's millisecond
            # timestamps cannot resolve a one-tick clamp when frames flush at EOF.
            assert command[-4] == "-f"
            command[-3] = "nut"
            process = subprocess.Popen(command,
                                       stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            sent_at = []
            try:
                due = time.monotonic()
                for index in range(1, 9):
                    time.sleep(max(0, due - time.monotonic()))
                    process.stdin.write(synthetic_jpeg(config.width, config.height, index))
                    process.stdin.flush()
                    sent_at.append(time.monotonic())
                    due += 1 / config.fps + (0.2 if index == 4 else 0)
                process.stdin.close()
                process.stdin = None
                _, encoder_stderr = process.communicate(timeout=10)
            finally:
                if process.poll() is None:
                    process.kill()
                    process.wait()
            probe = subprocess.run([args.ffprobe, "-v", "error", "-select_streams", "v:0", "-count_frames",
                                    "-show_entries", "stream=codec_name,profile,width,height,nb_read_frames,has_b_frames:frame=best_effort_timestamp_time",
                                    "-of", "json", str(path)], capture_output=True, timeout=10, check=False)
            probed = json.loads(probe.stdout) if probe.returncode == 0 else {}
            stream = probed.get("streams", [{}])[0]
            pts = [float(frame["best_effort_timestamp_time"]) for frame in probed.get("frames", []) if "best_effort_timestamp_time" in frame]
            deltas = [round(b - a, 6) for a, b in zip(pts, pts[1:])]
            timeline_verified = len(pts) == 8 and all(value > 0 for value in deltas) and max(deltas) >= 0.2
            encoder = {"attempted": True, "encoder": "libx264", "ffmpegExit": process.returncode,
                       "ffprobeExit": probe.returncode, "stream": stream,
                       "verified": process.returncode == probe.returncode == 0 and stream.get("codec_name") == "h264"
                       and stream.get("profile") == "Constrained Baseline" and stream.get("has_b_frames") == 0
                       and stream.get("nb_read_frames") == "8" and stream.get("width") == 640 and stream.get("height") == 480 and timeline_verified,
                       "wallClockFilterPts": True, "timestampTimeBase": "1/90000", "validationContainer": "nut",
                       "decodedPtsSeconds": pts, "decodedPtsDeltasSeconds": deltas,
                       "deliberateInputPauseSeconds": 0.2, "timelineGapPreserved": timeline_verified,
                       "inputReceiptTimesRelativeSeconds": [round(value - sent_at[0], 3) for value in sent_at],
                       "configuredBitrateKbps": config.bitrate_kbps,
                       "outputBytes": path.stat().st_size if path.exists() else 0,
                       "sha256": hashlib.sha256(path.read_bytes()).hexdigest() if path.exists() else None,
                       "temporaryOutputRemoved": True}
            (args.output / "encoder.log").write_bytes(encoder_stderr + probe.stderr)
    files = {}
    for path in sorted(ROOT.rglob("*")):
        if not path.is_file() or any(part in {".venv", ".runtime", "__pycache__", ".pytest_cache", "verification"} for part in path.relative_to(ROOT).parts):
            continue
        files[str(path.relative_to(ROOT))] = hashlib.sha256(path.read_bytes()).hexdigest()
    report = {"checkedAt": datetime.now(timezone.utc).isoformat(), "sourceMode": "simulation",
              "python": platform.python_version(), "dependencies": {name: importlib.metadata.version(name) for name in ("websockets", "Pillow")},
              "tests": {"run": result.testsRun, "failures": len(result.failures), "errors": len(result.errors), "skipped": len(result.skipped)},
              "softwareEncoder": encoder, "realCameraOpened": False, "physicalVerification": False,
              "mediaMtxIntegrationTested": False, "networkScope": "loopback fixture WebSocket and status HTTP tests only",
              "sourceHashes": files}
    (args.output / "result.json").write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps({"testsPassed": result.wasSuccessful(), "tests": result.testsRun,
                      "softwareEncoderVerified": encoder["verified"], "result": str(args.output / "result.json")}))
    return 0 if result.wasSuccessful() and encoder["verified"] else 1


if __name__ == "__main__":
    raise SystemExit(main())

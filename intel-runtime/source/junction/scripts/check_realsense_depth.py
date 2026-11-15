#!/usr/bin/env python3
"""Capture D415 color/depth/stereo IR after all other camera users have closed."""

import argparse
import json
from pathlib import Path
import signal
import subprocess
import sys
import time


def arguments():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--serial", required=True, help="RealSense SDK serial, not USB serial")
    parser.add_argument("--output-dir", type=Path, required=True, help="New, nonexistent directory")
    parser.add_argument("--worker", action="store_true", help=argparse.SUPPRESS)
    return parser.parse_args()


def terminate(process):
    process.terminate()
    try:
        process.wait(timeout=2)
    except subprocess.TimeoutExpired:
        process.kill()
        process.wait(timeout=1)


def supervise(args):
    args.output_dir.mkdir(parents=True, exist_ok=False)
    process = subprocess.Popen([sys.executable, str(Path(__file__).resolve()), *sys.argv[1:], "--worker"])
    try:
        return process.wait(timeout=40)
    except (subprocess.TimeoutExpired, KeyboardInterrupt) as error:
        terminate(process)
        result = {"status": "interrupted", "reason": type(error).__name__, "serial": args.serial}
        (args.output_dir / "watchdog.json").write_text(json.dumps(result, indent=2) + "\n")
        print(json.dumps(result), file=sys.stderr)
        return 124 if isinstance(error, subprocess.TimeoutExpired) else 130


def interrupted(signum, _frame):
    raise TimeoutError(f"Capture interrupted by signal {signum}")


def capture(args):
    signal.signal(signal.SIGTERM, interrupted)
    report = {"serial": args.serial, "requested_duration_s": 5, "status": "error"}
    pipeline, started, latest = None, False, {}
    exit_code = 1
    try:
        import importlib.metadata
        import cv2
        import numpy as np
        import pyrealsense2 as rs

        report["pyrealsense2_version"] = importlib.metadata.version("pyrealsense2")
        context = rs.context()
        devices = list(context.query_devices())
        report["discovered_devices"] = [
            {"name": d.get_info(rs.camera_info.name), "serial": d.get_info(rs.camera_info.serial_number)}
            for d in devices
        ]
        device = next((d for d in devices if d.get_info(rs.camera_info.serial_number) == args.serial), None)
        if device is None:
            raise RuntimeError("Requested SDK serial was not found")
        if device.supports(rs.camera_info.usb_type_descriptor):
            report["usb_type"] = device.get_info(rs.camera_info.usb_type_descriptor)

        def profile_key(profile):
            video = profile.as_video_stream_profile()
            return (str(profile.stream_type()), profile.stream_index(), video.width(),
                    video.height(), str(profile.format()), profile.fps())

        available = {
            profile_key(p) for sensor in device.query_sensors()
            for p in sensor.get_stream_profiles() if p.is_video_stream_profile()
        }
        report["profile_columns"] = ["stream", "index", "width", "height", "format", "fps"]
        report["available_video_profiles"] = sorted(available)
        specs = [("color", rs.stream.color, 0, rs.format.rgb8),
                 ("depth", rs.stream.depth, 0, rs.format.z16),
                 ("left_ir", rs.stream.infrared, 1, rs.format.y8),
                 ("right_ir", rs.stream.infrared, 2, rs.format.y8)]
        requested = [(str(stream), index, 640, 480, str(fmt), 30) for _, stream, index, fmt in specs]
        report["requested_profiles"] = requested
        report["missing_profiles"] = [p for p in requested if p not in available]
        if report["missing_profiles"]:
            raise RuntimeError("Required profiles unavailable; no fallback was attempted")

        config = rs.config()
        config.enable_device(args.serial)
        for _, stream, index, fmt in specs:
            config.enable_stream(stream, index, 640, 480, fmt, 30)
        pipeline = rs.pipeline(context)
        active = pipeline.start(config)
        started = True
        report["active_profiles"] = [profile_key(p) for p in active.get_streams()]
        if set(map(tuple, report["active_profiles"])) != set(requested):
            raise RuntimeError("Active profiles differ from requested profiles")
        report["timeouts"] = {"warmup": 0, "measurement": 0}

        def wait(phase):
            try:
                return pipeline.wait_for_frames(timeout_ms=1000)
            except RuntimeError as error:
                if "didn't arrive" not in str(error).lower() and "timeout" not in str(error).lower():
                    raise
                report["timeouts"][phase] += 1
                return None

        warmup_start, warmup_ids = time.monotonic(), set()
        while len(warmup_ids) < 30:
            if time.monotonic() - warmup_start >= 10:
                raise TimeoutError("Could not collect 30 distinct warmup depth frames within 10 seconds")
            frames = wait("warmup")
            depth = frames.get_depth_frame() if frames else None
            if depth:
                warmup_ids.add(depth.get_frame_number())
        report["warmup_unique_depth_frames"] = len(warmup_ids)
        stats = {name: {"unique_frames": 0, "reused_frames": 0, "missing_framesets": 0,
                        "frame_number_gaps": 0, "frame_number_regressions": 0}
                 for name, *_ in specs}
        seen = {name: set() for name in stats}
        valid_fractions = []
        measurement_start = time.monotonic()
        while time.monotonic() - measurement_start < 5:
            frames = wait("measurement")
            if frames is None:
                continue
            received = {"color": frames.get_color_frame(), "depth": frames.get_depth_frame(),
                        "left_ir": frames.get_infrared_frame(1), "right_ir": frames.get_infrared_frame(2)}
            for name, frame in received.items():
                metric = stats[name]
                if not frame:
                    metric["missing_framesets"] += 1
                    continue
                number = frame.get_frame_number()
                if number in seen[name]:
                    metric["reused_frames"] += 1
                    continue
                seen[name].add(number)
                previous = metric.get("last_frame_number")
                if previous is not None:
                    metric["frame_number_gaps"] += max(0, number - previous - 1)
                    metric["frame_number_regressions"] += int(number < previous)
                metric.setdefault("first_frame_number", number)
                metric["last_frame_number"] = number
                metric["unique_frames"] += 1
                metric["last_timestamp_ms"] = frame.get_timestamp()
                metric["timestamp_domain"] = str(frame.get_frame_timestamp_domain())
                latest[name] = np.asanyarray(frame.get_data()).copy()
                if name == "depth":
                    report["depth_units_m"] = frame.get_units()
                    valid_fractions.append(float(np.count_nonzero(latest[name]) / latest[name].size))
        report["measurement_duration_s"] = time.monotonic() - measurement_start
        for metric in stats.values():
            metric["observed_unique_fps"] = metric["unique_frames"] / report["measurement_duration_s"]
        report["streams"] = stats
        if valid_fractions:
            report["depth_nonzero_fraction"] = {"mean": float(np.mean(valid_fractions)),
                                                 "min": min(valid_fractions), "max": max(valid_fractions)}
        units = report.get("depth_units_m", 0)
        if not np.isfinite(units) or units <= 0:
            raise RuntimeError("No valid depth scaling factor was received")

        def save(name, array):
            if not cv2.imwrite(str(args.output_dir / name), array):
                raise OSError(f"Could not save {name}")

        if "color" in latest:
            save("color.jpg", cv2.cvtColor(latest["color"], cv2.COLOR_RGB2BGR))
        for name in ("left_ir", "right_ir"):
            if name in latest:
                save(name + ".png", latest[name])
        if "depth" in latest:
            depth_image = latest["depth"]
            save("depth_raw16.png", depth_image)
            valid = depth_image > 0
            depths_m = depth_image[valid].astype(np.float64) * units
            report["last_frame_depth_percentiles_m"] = (
                dict(zip(("p05", "p50", "p95"), np.percentile(depths_m, [5, 50, 95]).tolist()))
                if depths_m.size else None)
            scaled = np.clip(depth_image.astype(np.float64) * units / 2 * 255, 0, 255).astype(np.uint8)
            visualization = cv2.applyColorMap(scaled, cv2.COLORMAP_TURBO)
            visualization[~valid] = 0
            save("depth_visualization_not_metric.png", visualization)
            report["depth_visualization"] = "Color map clipped to 0–2 m; black=invalid. Use raw16 × depth_units_m for measurements."
        report["basic_checks"] = {"all_streams_have_multiple_unique_frames": all(m["unique_frames"] >= 2 for m in stats.values()),
                                  "some_nonzero_depth": bool(valid_fractions and max(valid_fractions) > 0)}
        report["limitations"] = "Nonzero depth measures coverage, not depth accuracy; frame-number gaps can include application drops."
        exit_code = 0 if all(report["basic_checks"].values()) else 2
        report["status"] = "completed" if exit_code == 0 else "incomplete"
    except Exception as error:
        report["error"] = f"{type(error).__name__}: {error}"
    finally:
        if started:
            try:
                pipeline.stop()
                report["pipeline_stopped"] = True
            except Exception as error:
                report["stop_error"] = f"{type(error).__name__}: {error}"
                report["status"], exit_code = "error", 1
        (args.output_dir / "report.json").write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps({"status": report["status"], "report": str(args.output_dir / "report.json")}))
    return exit_code


if __name__ == "__main__":
    args = arguments()
    sys.exit(capture(args) if args.worker else supervise(args))

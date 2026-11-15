#!/usr/bin/env python3
"""Capture temporary Studio previews; run inside the existing Studio container."""

import argparse
import asyncio
from datetime import datetime, timezone
import hashlib
from io import BytesIO
import json
from pathlib import Path
import re
import time
from urllib.parse import urlencode
from urllib.request import urlopen


def get_json(url):
    with urlopen(url, timeout=15) as response:
        return json.load(response)


def select_external(devices):
    selected, skipped, seen = [], [], set()
    native_realsense = any(camera.get("driver") == "realsense" for camera in devices)
    for camera in devices:
        driver, fingerprint = camera.get("driver"), camera.get("fingerprint", {})
        reason = None
        if driver == "usb_camera":
            if native_realsense and "realsense" in camera.get("name", "").lower():
                reason = "RealSense UVC alias; prefer native RealSense driver."
            elif not str(fingerprint.get("bus", "")).startswith("usb-"):
                reason = "Not an external USB camera."
        elif driver != "realsense":
            reason = "Driver outside this check."
        identity = json.dumps([driver, {k: v for k, v in fingerprint.items() if k != "index"}], sort_keys=True)
        if identity in seen:
            reason = "Duplicate hardware fingerprint."
        if reason:
            skipped.append({"camera": camera, "reason": reason})
        else:
            seen.add(identity)
            selected.append(camera)
    return selected, skipped


def choose_profile(formats, driver):
    candidates = [
        (int(item["width"]), int(item["height"]), int(fps))
        for item in formats for fps in item["fps"]
        if (424 if driver == "realsense" else 160) <= int(item["width"]) <= (1920 if driver == "realsense" else 4096)
        and (240 if driver == "realsense" else 120) <= int(item["height"]) <= (1080 if driver == "realsense" else 2160)
        and (6 if driver == "realsense" else 1) <= int(fps) <= (90 if driver == "realsense" else 120)
    ]
    if not candidates:
        raise ValueError("No reported formats fit the Studio preview schema.")
    width, height, fps = min(candidates, key=lambda p: (abs(p[0] - 640) + abs(p[1] - 480), abs(p[2] - 30)))
    return {"width": width, "height": height, "fps": fps}


def jpeg_dimensions(message):
    from PIL import Image
    if isinstance(message, str):
        raise RuntimeError(f"Studio WebSocket message: {message[:2000]}")
    with Image.open(BytesIO(message)) as frame:
        if frame.format != "JPEG":
            raise ValueError("Preview message is not JPEG.")
        frame.load()
        return frame.size


def save_json(path, data):
    with path.open("x", encoding="utf-8") as target:
        json.dump(data, target, indent=2, ensure_ascii=False)
        target.write("\n")


async def capture(base_url, camera, profile, seconds, output_dir, phase, barrier=None, startup_delay=0):
    from websockets.asyncio.client import connect
    config = {"name": camera["name"], "hardware_name": camera["name"], "driver": camera["driver"],
              "fingerprint": camera["fingerprint"], "payload": profile}
    ws_base = re.sub(r"^http", "ws", base_url)
    url = ws_base + "/api/cameras/ws?" + urlencode({"camera": json.dumps(config)})
    digest = hashlib.sha256(json.dumps(config["fingerprint"], sort_keys=True).encode()).hexdigest()[:10]
    stem = phase + "-" + re.sub(r"[^a-zA-Z0-9_-]+", "_", camera["name"])[:60] + "-" + digest
    result = {"camera": camera, "requested_profile": profile, "phase": phase, "ok": False,
              "frame_count": 0, "preview_fps": None, "dimensions": [], "errors": [],
              "startup_delay_seconds": startup_delay}
    if startup_delay:
        await asyncio.sleep(startup_delay)
    started, first, last, last_jpeg = time.monotonic(), None, None, None
    dimensions = set()
    try:
        if barrier is not None and barrier.broken:
            raise RuntimeError("Concurrent startup cancelled after another camera failed.")
        async with asyncio.timeout(20 + seconds + 15):
            async with connect(url, open_timeout=10, close_timeout=3, max_size=20 * 1024**2,
                               max_queue=1, proxy=None) as websocket:
                message = await asyncio.wait_for(websocket.recv(), max(0.01, 20 - (time.monotonic() - started)))
                jpeg_dimensions(message)
                result["startup_seconds"] = round(time.monotonic() - started, 3)
                if barrier is not None:
                    await asyncio.wait_for(barrier.wait(), timeout=20)
                # Drain startup backlog before measuring delivery through the preview endpoint.
                warmup_end = time.monotonic() + 0.5
                while time.monotonic() < warmup_end:
                    message = await asyncio.wait_for(websocket.recv(), timeout=10)
                    jpeg_dimensions(message)
                end = time.monotonic() + seconds
                while time.monotonic() < end:
                    try:
                        message = await asyncio.wait_for(websocket.recv(), min(10, end - time.monotonic()))
                    except TimeoutError:
                        if time.monotonic() >= end:
                            break
                        raise RuntimeError("No preview frame received for 10 seconds.")
                    size = jpeg_dimensions(message)
                    received = time.monotonic()
                    first = received if first is None else first
                    last, last_jpeg = received, message
                    dimensions.add(size)
                    result["frame_count"] += 1
            result["client_websocket_closed"] = True
        result["ok"] = result["frame_count"] >= 2
        if result["frame_count"] < 2:
            result["errors"].append("Fewer than two measured frames received.")
        if dimensions != {(profile["width"], profile["height"])}:
            result["ok"] = False
            result["errors"].append("Decoded frame dimensions do not consistently match the requested profile.")
    except Exception as exc:
        result["errors"].append(f"{type(exc).__name__}: {exc}")
        if barrier is not None:
            await barrier.abort()
    result["elapsed_seconds"] = round(time.monotonic() - started, 3)
    result["dimensions"] = [list(size) for size in sorted(dimensions)]
    result["first_frame_monotonic"], result["last_frame_monotonic"] = first, last
    if first is not None and last is not None and last > first:
        result["preview_fps"] = round((result["frame_count"] - 1) / (last - first), 2)
    if last_jpeg is not None:
        image_path = output_dir / (stem + ".jpg")
        with image_path.open("xb") as target:
            target.write(last_jpeg)
        result["frame_file"] = image_path.name
    save_json(output_dir / (stem + ".json"), result)
    return result


async def run(args, report):
    devices = await asyncio.to_thread(get_json, args.base_url + "/api/hardware/cameras?all=true")
    cameras, report["skipped"] = select_external(devices)
    report["discovered_count"] = len(devices)
    prepared = []
    for camera in cameras:
        item = {"camera": camera}
        report["formats"].append(item)
        try:
            url = args.base_url + "/api/cameras/supported_formats/" + camera["driver"] + "?" + urlencode({"fingerprint": json.dumps(camera["fingerprint"])})
            item["supported"] = await asyncio.to_thread(get_json, url)
            item["selected"] = choose_profile(item["supported"], camera["driver"])
            prepared.append((camera, item["selected"]))
        except Exception as exc:
            item["error"] = f"{type(exc).__name__}: {exc}"
            report["errors"].append(f"Format query failed for {camera['name']}: {exc}")
    if not args.concurrent_only:
        for camera, profile in prepared:
            report["sequential"].append(await capture(args.base_url, camera, profile, args.seconds, args.output_dir, "sequential"))
            await asyncio.sleep(args.release_wait_seconds)  # Idle expiry is followed by camera/publisher teardown.
    if args.concurrent:
        if len(prepared) < 2 or report["errors"] or not all(item["ok"] for item in report["sequential"]):
            report["errors"].append("Concurrent check requires at least two cameras and all individual checks to pass.")
        else:
            barrier = asyncio.Barrier(len(prepared))
            report["concurrent"] = await asyncio.gather(*[
                capture(args.base_url, camera, profile, args.seconds, args.output_dir, "concurrent", barrier,
                        startup_delay=index * args.startup_gap_seconds)
                for index, (camera, profile) in enumerate(prepared)
            ])
            results = report["concurrent"]
            if all(item["ok"] for item in results):
                overlap = min(item["last_frame_monotonic"] for item in results) - max(item["first_frame_monotonic"] for item in results)
                report["concurrent_overlap_seconds"] = round(max(0, overlap), 3)
                if overlap < args.seconds / 2:
                    report["errors"].append("Insufficient simultaneous frame-delivery overlap.")
            await asyncio.sleep(args.release_wait_seconds)
    if not cameras:
        report["errors"].append("No external USB or native RealSense cameras were discovered.")


def main():
    parser = argparse.ArgumentParser(description=__doc__ + " Saves actual JPEG frames and JSON; does not create project cameras. Preview FPS measures JPEG delivery, not native sensor FPS. --concurrent runs only after individual checks pass.")
    parser.add_argument("--output-dir", required=True, type=Path, help="new output directory; existing directories are refused")
    parser.add_argument("--base-url", default="http://127.0.0.1:7860")
    parser.add_argument("--seconds", type=float, default=5)
    parser.add_argument("--concurrent", action="store_true")
    parser.add_argument("--concurrent-only", action="store_true", help="skip individual tests; use after earlier successful individual checks")
    parser.add_argument("--startup-gap-seconds", type=float, default=0, help="gap between concurrent socket openings (default: 0); measurements still run together")
    parser.add_argument("--release-wait-seconds", type=float, default=10, help="wait after client closure for publisher idle expiry and teardown (default: 10)")
    args = parser.parse_args()
    if not 1 <= args.seconds <= 60:
        parser.error("--seconds must be between 1 and 60")
    if not 0 <= args.startup_gap_seconds <= 5:
        parser.error("--startup-gap-seconds must be between 0 and 5")
    if not 5 <= args.release_wait_seconds <= 60:
        parser.error("--release-wait-seconds must be between 5 and 60")
    args.concurrent = args.concurrent or args.concurrent_only
    args.base_url = args.base_url.rstrip("/")
    args.output_dir.mkdir(parents=True, exist_ok=False)
    report = {"timestamp_utc": datetime.now(timezone.utc).isoformat(), "formats": [], "sequential": [],
              "individual_checks_skipped": args.concurrent_only, "startup_gap_seconds": args.startup_gap_seconds,
              "release_wait_seconds": args.release_wait_seconds,
              "concurrent": [], "errors": [], "notes": [
                  "Preview delivery FPS includes camera capture, JPEG encoding, transport and decoding; it is not native sensor FPS.",
                  "Native RealSense preview starts RGB and depth streams, but these saved JPEGs validate RGB only.",
                  "Client sockets close on exit; the configured release wait allows for publisher idle expiry plus teardown. Other subscribers can keep a camera open.",
                  "Concurrent success tests simultaneous streams on their current USB wiring; it does not establish the physical hub topology.",
                  "Concurrent-only is a separate diagnostic; it neither repeats nor replaces earlier individual or simultaneous-start results.",
              ]}
    try:
        asyncio.run(run(args, report))
    except (Exception, KeyboardInterrupt) as exc:
        report["errors"].append(f"{type(exc).__name__}: {exc}")
    results = report["sequential"] + report["concurrent"]
    report["ok"] = bool(results) and not report["errors"] and all(item["ok"] for item in results)
    save_json(args.output_dir / "report.json", report)
    print(json.dumps(report, indent=2, ensure_ascii=False))
    return 0 if report["ok"] else 2


if __name__ == "__main__":
    raise SystemExit(main())

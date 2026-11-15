#!/usr/bin/env python3
"""Read-only host/device inventory, with optional synthetic inference.

Never connects to a camera or serial port, and never sends robot commands.
Passing the software check does not establish calibration or physical success.
"""
from __future__ import annotations

import argparse
import ctypes.util
import importlib.metadata
import json
import os
import platform
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path


def read_text(path: Path) -> str:
    try:
        return path.read_text().strip()
    except (OSError, UnicodeError):
        return ""


def device_nodes(pattern: str) -> list[dict]:
    return [
        {"path": str(path), "readable": os.access(path, os.R_OK),
         "writable": os.access(path, os.W_OK)}
        for path in sorted(Path("/dev").glob(pattern))
    ]


def inventory() -> dict:
    cpu_fields = {}
    for line in read_text(Path("/proc/cpuinfo")).splitlines():
        key, separator, value = line.partition(":")
        if separator and key.strip() in {"vendor_id", "model name"}:
            cpu_fields.setdefault(key.strip(), value.strip())
    os_fields = {}
    for line in read_text(Path("/etc/os-release")).splitlines():
        key, separator, value = line.partition("=")
        if separator:
            os_fields[key] = value.strip('"')
    pci = []
    for path in sorted(Path("/sys/bus/pci/devices").glob("*")):
        device_class = read_text(path / "class")
        if device_class.startswith(("0x03", "0x12")):
            driver = path / "driver"
            pci.append({"address": path.name, "vendor": read_text(path / "vendor"),
                        "device": read_text(path / "device"), "class": device_class,
                        "driver": driver.resolve().name if driver.exists() else None})
    model = cpu_fields.get("model name", "")
    target_candidate = (
        platform.system() == "Linux"
        and platform.machine() == "x86_64"
        and os_fields.get("ID") == "ubuntu"
        and cpu_fields.get("vendor_id") == "GenuineIntel"
        and "core" in model.lower() and "ultra" in model.lower()
    )
    return {
        "checked_at": datetime.now(timezone.utc).isoformat(),
        "evidence_kind": "host_inventory",
        "physical_cycle_tested": False,
        "system": platform.system(), "architecture": platform.machine(),
        "os": os_fields.get("PRETTY_NAME", platform.platform()),
        "cpu": cpu_fields or None,
        "intel_core_ultra_host_candidate": target_candidate,
        "exact_challenge_station_confirmed": False,
        "pci_accelerators": pci,
        "device_nodes": {
            "gpu": device_nodes("dri/renderD*"),
            "npu": device_nodes("accel/accel*"),
            "camera": device_nodes("video*"),
            "serial_by_id": device_nodes("serial/by-id/*"),
            "serial_tty": device_nodes("ttyACM*") + device_nodes("ttyUSB*"),
        },
        "native_libraries": {
            name: ctypes.util.find_library(name)
            for name in ("GL", "glib-2.0", "usb-1.0", "turbojpeg", "avcodec")
        },
        "commands": {name: shutil.which(name) for name in ("uv", "ffmpeg", "git")},
        "notes": [
            "Brev/SSH access does not identify the physical challenge station.",
            "Device nodes and permissions do not prove camera capture, robot calibration, or motion.",
        ],
    }


def runtime_check() -> dict:
    result = {"evidence_kind": "synthetic_software_smoke", "packages": {},
              "openvino_devices": [], "inference": {}}
    for name in ("physicalai-studio", "physicalai", "physicalai-train", "anomalib",
                 "openvino", "torch", "torchvision", "pyrealsense2"):
        try:
            result["packages"][name] = importlib.metadata.version(name)
        except importlib.metadata.PackageNotFoundError:
            result["packages"][name] = None
    try:
        import numpy as np
        import openvino as ov
        from openvino import opset13 as ops
        core = ov.Core()
        devices = list(core.available_devices)
        result["openvino_devices"] = devices
        data = np.array([[-1.0, 2.0, -3.0, 4.0]], dtype=np.float32)
        parameter = ops.parameter(data.shape, ov.Type.f32, name="input")
        model = ov.Model([ops.relu(parameter)], [parameter], "setup_relu")
        for family in ("CPU", "GPU", "NPU"):
            matches = [d for d in devices if d.split(".")[0] == family]
            if not matches:
                result["inference"][family] = {"status": "unavailable"}
            for device in matches:
                try:
                    compiled = core.compile_model(model, device)
                    actual = compiled([data])[compiled.output(0)]
                    np.testing.assert_allclose(actual, np.maximum(data, 0))
                    result["inference"][device] = {
                        "status": "passed", "full_name": core.get_property(device, "FULL_DEVICE_NAME"),
                        "model": "four-element ReLU; not a challenge model",
                    }
                except Exception as error:
                    result["inference"][device] = {"status": "failed", "error": str(error)}
    except Exception as error:
        result["openvino_error"] = str(error)
    try:
        import torch
        result["torch"] = {
            "version": torch.__version__,
            "xpu_available": bool(hasattr(torch, "xpu") and torch.xpu.is_available()),
            "cuda_available": torch.cuda.is_available(),
        }
    except Exception as error:
        result["torch_error"] = str(error)
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--runtime", action="store_true", help="Run synthetic OpenVINO inference.")
    parser.add_argument("--require-host", action="store_true", help="Require an Ubuntu x86_64 Intel Core Ultra host.")
    parser.add_argument("--require-devices", nargs="+", choices=("CPU", "GPU", "NPU"), default=[])
    parser.add_argument("--output", type=Path, help="Also save the JSON evidence to this file.")
    args = parser.parse_args()
    if args.require_devices and not args.runtime:
        parser.error("--require-devices requires --runtime")
    report = inventory()
    failures = []
    if args.require_host and not report["intel_core_ultra_host_candidate"]:
        failures.append("This host is not identified as the Ubuntu Intel Core Ultra target.")
    if args.runtime:
        report["runtime"] = runtime_check()
        checks = report["runtime"]["inference"]
        if report["runtime"].get("openvino_error") or report["runtime"].get("torch_error"):
            failures.append("A required inference runtime could not be loaded.")
        if not report["runtime"]["openvino_devices"]:
            failures.append("OpenVINO did not enumerate an inference device.")
        if any(value["status"] == "failed" for value in checks.values()):
            failures.append("An enumerated OpenVINO device failed synthetic inference.")
        for family in args.require_devices:
            matching = [v for k, v in checks.items() if k.split(".")[0] == family]
            if not matching or not all(v["status"] == "passed" for v in matching):
                failures.append(f"Synthetic inference was not confirmed on {family}.")
    report["requested_checks_passed"] = not failures
    report["failures"] = failures
    encoded = json.dumps(report, indent=2) + "\n"
    print(encoded, end="")
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(encoded)
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())

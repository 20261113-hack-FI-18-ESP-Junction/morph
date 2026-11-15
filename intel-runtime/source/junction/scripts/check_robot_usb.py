#!/usr/bin/env python3
"""Read-only USB inventory; never opens a serial device or sends robot commands."""

import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import stat
import subprocess
import sys


def inventory():
    result = {
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "scope": "USB inventory only; does not establish communication with motors.",
        "identity": {
            "uid": os.getuid(),
            "effective_uid": os.geteuid(),
            "effective_gid": os.getegid(),
            "supplementary_gids": os.getgroups(),
        },
        "permissions_scope": "Access checks apply only to this process and its device namespace.",
        "directories": {},
        "serial_nodes": [],
        "video_nodes": [],
        "usb_devices": [],
        "errors": [],
    }

    def entries(directory):
        try:
            paths = sorted(Path(directory).iterdir())
        except FileNotFoundError:
            result["directories"][directory] = "absent"
            return []
        except OSError as exc:
            result["directories"][directory] = "error"
            result["errors"].append({"path": directory, "error": str(exc)})
            return []
        result["directories"][directory] = "present"
        return paths

    for directory in ("/dev", "/dev/serial/by-id", "/dev/serial/by-path", "/sys/class/tty", "/sys/class/video4linux"):
        for path in entries(directory):
            prefixes = ("ttyACM", "ttyUSB", "video") if directory == "/dev" else ("ttyACM", "ttyUSB")
            if directory in ("/dev", "/sys/class/tty") and not path.name.startswith(prefixes):
                continue
            node = {"path": str(path)}
            try:
                node["resolved_path"] = os.path.realpath(path)
                info = path.stat()
                node.update({
                    "mode": stat.filemode(info.st_mode),
                    "uid": info.st_uid,
                    "gid": info.st_gid,
                    "readable": os.access(path, os.R_OK, effective_ids=True),
                    "writable": os.access(path, os.W_OK, effective_ids=True),
                })
            except OSError as exc:
                node["error"] = str(exc)
                result["errors"].append({"path": str(path), "error": str(exc)})
            is_video = directory == "/sys/class/video4linux" or (directory == "/dev" and path.name.startswith("video"))
            if is_video:
                sysfs = Path("/sys/class/video4linux") / path.name
                try:
                    node["name"] = (sysfs / "name").read_text().strip()
                    node["device_path"] = str((sysfs / "device").resolve(strict=True))
                except OSError as exc:
                    node["metadata_error"] = str(exc)
                    result["errors"].append({"path": str(sysfs), "error": str(exc)})
            result["video_nodes" if is_video else "serial_nodes"].append(node)

    for path in entries("/sys/bus/usb/devices"):
        device = {"sysfs_path": str(path)}
        for field in (
            "idVendor", "idProduct", "manufacturer", "product", "serial",
            "authorized", "authorized_default", "speed", "power/control", "power/runtime_status",
        ):
            try:
                device[field] = (path / field).read_text().strip()
            except FileNotFoundError:
                continue  # USB interfaces and optional descriptors lack these files.
            except OSError as exc:
                result["errors"].append({"path": str(path / field), "error": str(exc)})
        if "idVendor" in device or "idProduct" in device:
            result["usb_devices"].append(device)
    return result


def container_inventory(name):
    command = ["docker", "exec", "-i", name, "python", "-", "--inventory-only"]
    try:
        completed = subprocess.run(
            command, input=Path(__file__).read_text(), text=True,
            capture_output=True, timeout=20, check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        return {"name": name, "error": str(exc)}
    if completed.returncode != 0:
        return {
            "name": name, "error": "Container inventory command failed.",
            "returncode": completed.returncode,
            "stderr": completed.stderr[-4000:], "stdout": completed.stdout[-4000:],
        }
    try:
        data = json.loads(completed.stdout)
        if not isinstance(data, dict) or any(
            not isinstance(data.get(key), list) for key in ("serial_nodes", "video_nodes", "usb_devices", "errors")
        ):
            raise ValueError("Unexpected inventory structure")
    except (ValueError, TypeError) as exc:
        return {"name": name, "error": str(exc), "stdout": completed.stdout[-4000:],
                "stderr": completed.stderr[-4000:]}
    return {"name": name, "inventory": data}


def compare(host, container):
    comparison = {}
    for label, key, field in (
        ("serial_paths", "serial_nodes", "path"),
        ("video_paths", "video_nodes", "path"),
        ("usb_sysfs_paths", "usb_devices", "sysfs_path"),
    ):
        host_paths = {item[field] for item in host[key]}
        container_paths = {item[field] for item in container[key]}
        comparison[label] = {
            "both": sorted(host_paths & container_paths),
            "host_only": sorted(host_paths - container_paths),
            "container_only": sorted(container_paths - host_paths),
        }
    comparison["note"] = "Snapshots are sequential; shared paths do not prove motor connectivity or device access."
    return comparison


def main():
    parser = argparse.ArgumentParser(
        description="List USB, serial-device and video-device metadata as JSON without opening devices or capturing images. "
                    "This inventory does not prove communication with motors. Permission checks "
                    "describe the current process only.",
    )
    parser.add_argument("--container", metavar="NAME", help="also inventory an existing Docker container and compare paths")
    parser.add_argument("--output", type=Path, metavar="PATH", help="save the JSON baseline exclusively; existing files are never overwritten")
    parser.add_argument("--inventory-only", action="store_true", help=argparse.SUPPRESS)
    args = parser.parse_args()
    if args.inventory_only and (args.container or args.output):
        parser.error("--inventory-only cannot be combined with --container or --output")

    result = inventory()
    failed = bool(result["errors"])
    if args.container:
        result["container"] = container_inventory(args.container)
        if "inventory" in result["container"]:
            other = result["container"]["inventory"]
            result["comparison"] = compare(result, other)
            failed = failed or bool(other["errors"])
        else:
            failed = True

    rendered = json.dumps(result, indent=2, ensure_ascii=False) + "\n"
    print(rendered, end="")
    if args.output:
        try:
            with args.output.open("x", encoding="utf-8") as target:
                target.write(rendered)
        except OSError as exc:
            print(f"Could not save baseline: {exc}", file=sys.stderr)
            failed = True
    return 2 if failed else 0


if __name__ == "__main__":
    sys.exit(main())

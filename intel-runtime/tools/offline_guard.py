"""Process-local audit guards for reviewed offline tests; not an OS sandbox."""
from __future__ import annotations

import atexit
import builtins
import importlib.abc
import io
import json
import os
from pathlib import Path
import signal
import socket
import subprocess
import sys

ATTEMPTS: list[dict[str, str]] = []
INSTALLED = False


def reject(kind: str):
    ATTEMPTS.append({"kind": kind})
    raise RuntimeError(f"Offline verification denied {kind}")


class HardwareImports(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname, path=None, target=None):
        if fullname.split(".")[0] in {"lerobot", "scservo_sdk", "serial", "pyrealsense2", "cv2"}:
            reject("real hardware library import")
        return None


def install():
    global INSTALLED
    if INSTALLED:
        return
    INSTALLED = True
    for name in ("connect", "connect_ex", "bind", "listen"):
        setattr(socket.socket, name, lambda *a, **k: reject("network or listener operation"))
    socket.getaddrinfo = lambda *a, **k: reject("DNS lookup")
    sys.meta_path.insert(0, HardwareImports())

    def checked_open(original):
        def call(file, *args, **kwargs):
            if isinstance(file, (str, bytes, os.PathLike)):
                raw = os.fsdecode(file)
                if raw.startswith("/dev/") and raw != "/dev/null":
                    reject("device open")
            return original(file, *args, **kwargs)
        return call

    builtins.open = checked_open(builtins.open)
    io.open = checked_open(io.open)
    os.open = checked_open(os.open)
    original_kill = os.kill

    def checked_kill(pid, sig):
        if pid != os.getpid() or sig != signal.SIGALRM:
            reject("external process signal")
        return original_kill(pid, sig)

    os.kill = checked_kill
    original_popen = subprocess.Popen
    guard_dir = str(Path(__file__).resolve().parent)

    def checked_popen(args, *rest, **kwargs):
        if not isinstance(args, (list, tuple)) or list(args[:3]) != [sys.executable, "-m", "morph_station.export_audit"]:
            reject("unreviewed subprocess")
        if kwargs.get("shell"):
            reject("shell subprocess")
        env = dict(kwargs.get("env") or os.environ)
        env["PYTHONPATH"] = guard_dir + os.pathsep + env.get("PYTHONPATH", "")
        env["MORPH_OFFLINE_GUARD"] = "1"
        kwargs["env"] = env
        return original_popen(args, *rest, **kwargs)

    subprocess.Popen = checked_popen

    def save_attempts():
        target = os.environ.get("MORPH_OFFLINE_REPORT_DIR")
        if target:
            Path(target, f"guard-{os.getpid()}.json").write_text(json.dumps({"pid": os.getpid(), "attempts": ATTEMPTS}) + "\n")

    atexit.register(save_attempts)

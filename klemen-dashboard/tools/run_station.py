#!/usr/bin/env python3
"""Launch an isolated complete simulation, or only the explicitly configured Mac dashboard."""
from __future__ import annotations

import argparse
from dataclasses import dataclass
import importlib.util
import json
import os
from pathlib import Path
import re
import secrets
import shutil
import signal
import socket
import stat
import subprocess
import sys
import tempfile
import threading
import time

from check_station import check, get_json
from prepare_demo_media import prepare as prepare_gateway
from run_local_demo import DASHBOARD, PACKAGE, STATION

BRIDGE = PACKAGE.parent / "intel-runtime/media-bridge"


class LaunchError(Exception):
    """Only fixed, credential-free descriptions may enter the public error channel."""


def prepared(relative: str) -> Path | None:
    return next((ancestor / ".junction-setup" / relative for ancestor in PACKAGE.parents
                 if (ancestor / ".junction-setup" / relative).is_file()), None)


def executable(explicit: str | None, name: str, prepared_path: str | None = None) -> str:
    candidate = explicit or (str(prepared(prepared_path)) if prepared_path and prepared(prepared_path) else None) or shutil.which(name)
    if not candidate or not Path(candidate).is_file() or not os.access(candidate, os.X_OK):
        raise LaunchError(f"Required {name} executable is unavailable; supply its explicit option.")
    return str(Path(candidate).absolute())


def environment(node: str) -> dict[str, str]:
    # No inherited provider, pairing, proxy, Python, Node options, or live media variables.
    result = {key: os.environ[key] for key in ("LANG", "LC_ALL", "TMPDIR") if key in os.environ}
    result["PATH"] = os.pathsep.join((str(Path(node).parent), "/usr/bin", "/bin", "/usr/sbin", "/sbin"))
    return result


def private_write(path: Path, value: str) -> None:
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as output:
        output.write(value)


def rewrite_generated(path: Path, value: str) -> None:
    # Called only for files generated inside this launcher's new private directory.
    fd = os.open(path, os.O_WRONLY | os.O_TRUNC | os.O_NOFOLLOW)
    with os.fdopen(fd, "w", encoding="utf-8") as output:
        output.write(value)


def private_path(path: Path, *, directory: bool) -> Path:
    info = path.lstat()
    if (not (stat.S_ISDIR(info.st_mode) if directory else stat.S_ISREG(info.st_mode)) or
            info.st_uid != os.getuid() or info.st_mode & 0o077):
        raise LaunchError("Explicit configuration must be owner-only and must not be a symlink.")
    return path.resolve(strict=True)


class Reservations:
    def __init__(self):
        self.sockets: dict[str, socket.socket] = {}
        self.ports: dict[str, int] = {}

    def reserve(self, name: str, port: int = 0, *, udp: bool = False) -> int:
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM if udp else socket.SOCK_STREAM)
        if not udp:
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            sock.bind(("127.0.0.1", port))
        except OSError:
            sock.close()
            raise LaunchError("Requested dashboard port is occupied or unavailable; choose another --port.") from None
        self.sockets[name], self.ports[name] = sock, sock.getsockname()[1]
        return self.ports[name]

    def release(self, *names: str) -> None:
        for name in names:
            sock = self.sockets.pop(name, None)
            if sock:
                sock.close()

    def close(self) -> None:
        self.release(*list(self.sockets))


@dataclass(frozen=True)
class ProcessIdentity:
    pid: int
    ppid: int
    pgid: int
    state: str
    started: str

    def matches(self, other) -> bool:
        return other is not None and self.pid == other.pid and self.pgid == other.pgid and self.started == other.started


def process_table() -> dict[int, ProcessIdentity]:
    result = subprocess.run(["/bin/ps", "-axo", "pid=,ppid=,pgid=,stat=,lstart="],
                            stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, timeout=3, check=False)
    if result.returncode:
        raise LaunchError("Owned process inspection is unavailable.")
    table = {}
    for line in result.stdout.decode("utf-8", "replace").splitlines():
        parts = line.split(maxsplit=4)
        if len(parts) == 5:
            try:
                entry = ProcessIdentity(*(int(x) for x in parts[:3]), parts[3], parts[4])
            except ValueError:
                continue
            table[entry.pid] = entry
    return table


class Child:
    def __init__(self, name: str, process: subprocess.Popen):
        self.name, self.process = name, process
        self.output_bytes, self.tail = 0, b""
        self.reader = threading.Thread(target=self.drain, daemon=True)
        self.reader.start()

    def drain(self):
        # Always drain pipe backpressure; retain at most 64 KiB privately, never echo it.
        with self.process.stdout as stream:
            while chunk := stream.read1(4096):
                self.output_bytes += len(chunk)
                self.tail = (self.tail + chunk)[-65536:]


class Supervisor:
    def __init__(self):
        process_table()  # Require a usable ownership probe before launching anything.
        self.children: list[Child] = []
        self.owned: dict[int, ProcessIdentity] = {}
        self.stopping = False

    def spawn(self, name: str, command: list[str], *, cwd: Path, env: dict) -> Child:
        if self.stopping:
            raise LaunchError("Launch interrupted.")
        child = Child(name, subprocess.Popen(command, cwd=cwd, env=env, stdin=subprocess.DEVNULL,
                                            stdout=subprocess.PIPE, stderr=subprocess.STDOUT, start_new_session=True))
        self.children.append(child)
        self.observe()
        return child

    def observe(self) -> dict[int, ProcessIdentity]:
        table = process_table()
        active = {pid for pid, identity in self.owned.items() if identity.matches(table.get(pid))}
        active.update(child.process.pid for child in self.children if child.process.poll() is None and child.process.pid in table)
        while True:
            more = {pid for pid, entry in table.items() if entry.ppid in active}
            if more <= active:
                break
            active.update(more)
        for pid in active:
            self.owned[pid] = table[pid]
        return table

    def healthy(self) -> None:
        self.observe()
        if self.stopping:
            raise LaunchError("Launch interrupted.")
        for child in self.children:
            if child.process.poll() is not None:
                raise LaunchError(f"Owned {child.name} process exited before shutdown.")

    def wait_json(self, port: int, route: str, predicate, *, token: str | None = None, timeout: float = 30) -> dict:
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            self.healthy()
            result = get_json(port, route, timeout=min(1, max(0.01, deadline - time.monotonic())), token=token)
            if result["status"] == "ok" and predicate(result["data"]):
                return result["data"]
            time.sleep(0.1)
        raise LaunchError("Owned services did not become ready before the startup deadline.")

    def _signal_owned_groups(self, sig: int, table: dict, *, direct_only: bool = False) -> None:
        groups = set()
        direct = {child.process.pid for child in self.children}
        for pid, identity in self.owned.items():
            current = table.get(pid)
            if identity.matches(current) and not current.state.startswith("Z") and current.pgid > 1 and current.pgid != os.getpgrp():
                if not direct_only or current.pgid in direct:
                    groups.add(current.pgid)
        for pgid in groups:
            try:
                os.killpg(pgid, sig)
            except ProcessLookupError:
                pass

    def close(self, *, grace: float = 25) -> dict:
        self.stopping = True
        table = self.observe()
        self._signal_owned_groups(signal.SIGTERM, table, direct_only=True)
        deadline = time.monotonic() + grace
        while time.monotonic() < deadline:
            for child in self.children:
                child.process.poll()
            table = self.observe()
            live = [entry for pid, entry in table.items() if pid in self.owned and self.owned[pid].matches(entry) and not entry.state.startswith("Z")]
            if not live:
                break
            # If all direct parents have stopped, their observed orphan groups still belong to us.
            if all(child.process.poll() is not None for child in self.children):
                self._signal_owned_groups(signal.SIGTERM, table)
            time.sleep(0.05)
        table = self.observe()
        self._signal_owned_groups(signal.SIGKILL, table)
        for child in self.children:
            try:
                child.process.wait(timeout=3)
            except subprocess.TimeoutExpired:
                pass
            child.reader.join(timeout=1)
            child.tail = b""
        table = self.observe()
        remaining = [entry for pid, entry in table.items() if pid in self.owned and self.owned[pid].matches(entry) and not entry.state.startswith("Z")]
        return {"ownedProcessesStopped": not remaining,
                "children": [{"name": child.name, "exitCode": child.process.poll(), "outputBytes": child.output_bytes}
                             for child in self.children], "observedOwnedProcessCount": len(self.owned)}


def local_preflight(command: list[str], *, cwd: Path, env: dict, expected: bytes | None = None) -> None:
    try:
        result = subprocess.run(command, cwd=cwd, env=env, stdin=subprocess.DEVNULL,
                                stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, timeout=10, check=False)
    except (OSError, subprocess.TimeoutExpired):
        raise LaunchError("Local dependency preflight failed; no service was started.") from None
    if result.returncode or expected is not None and expected not in result.stdout[:65536]:
        raise LaunchError("Local dependency preflight failed; verify prepared versions and dependencies.")


def prepare_media(directory: Path, ffmpeg: str, ports: dict, fps: int) -> Path:
    spec = importlib.util.spec_from_file_location("morph_synthetic_generator", BRIDGE / "tools/prepare_synthetic.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    module.prepare(directory, ffmpeg)
    bridge_path = directory / "bridge.json"
    bridge = json.loads(bridge_path.read_text())
    bridge["profile"]["fps"] = fps
    rewrite_generated(bridge_path, json.dumps(bridge))
    gateway_path = prepare_gateway(directory)
    gateway = json.loads(gateway_path.read_text())
    bridge["publisher"]["rtspUrl"] = f"rtsp://127.0.0.1:{ports['rtsp']}/inspection"
    bridge["status"]["port"] = ports["status"]
    gateway["whepUrl"] = f"http://127.0.0.1:{ports['whep']}/inspection/whep"
    gateway["statusUrl"] = f"http://127.0.0.1:{ports['status']}/api/media/v1/status"
    rewrite_generated(bridge_path, json.dumps(bridge))
    rewrite_generated(gateway_path, json.dumps(gateway))
    media_path = directory / "mediamtx.yml"
    media = media_path.read_text()
    for field, original, key in (("rtspAddress", 8554, "rtsp"), ("webrtcAddress", 8889, "whep"), ("webrtcLocalUDPAddress", 8189, "ice")):
        old = f"{field}: 127.0.0.1:{original}"
        if media.count(old) != 1:
            raise LaunchError("Synthetic media template has changed; review its topology before launching.")
        media = media.replace(old, f"{field}: 127.0.0.1:{ports[key]}")
    if "moq: false" not in media:
        raise LaunchError("Synthetic media template must explicitly disable MoQ.")
    rewrite_generated(media_path, media)
    return gateway_path


def launch_demo(args, supervisor: Supervisor, reservations: Reservations, runtime: Path, env: dict, node: str) -> dict:
    python = executable(args.python, "python3", "python/bin/python")
    ffmpeg = executable(args.ffmpeg, "ffmpeg")
    mediamtx = executable(args.mediamtx, "mediamtx", "live-video/mediamtx-v1.21.3/mediamtx")
    for name in ("rtsp", "whep", "status", "api"):
        reservations.reserve(name)
    reservations.reserve("ice", udp=True)
    ports = reservations.ports
    media_dir, records = runtime / "media", runtime / "records"
    gateway = prepare_media(media_dir, ffmpeg, ports, args.fps)
    records.mkdir(mode=0o700)
    private_write(records / "demo-instance.json", json.dumps({"mode": "disposable-simulation"}))
    token = secrets.token_urlsafe(48)
    token_file = records / "api-token"
    private_write(token_file, token)
    local_preflight([mediamtx, "--version"], cwd=runtime, env=env, expected=b"v1.21.3")
    local_preflight([python, "-m", "morph_media_bridge", "preflight", "--config", str(media_dir / "bridge.json")], cwd=BRIDGE, env=env)
    local_preflight([python, "-c", "import fastapi, uvicorn, pydantic"], cwd=STATION, env=env)
    reservations.release("rtsp", "whep", "ice")
    supervisor.spawn("media-server", [mediamtx, str(media_dir / "mediamtx.yml")], cwd=runtime, env=env)
    # A local TCP listener, not hardware or browser playback, is the media-server startup criterion.
    deadline = time.monotonic() + 10
    while True:
        supervisor.healthy()
        try:
            with socket.create_connection(("127.0.0.1", ports["rtsp"]), timeout=0.2):
                break
        except OSError:
            if time.monotonic() > deadline:
                raise LaunchError("Owned media server did not listen before its startup deadline.") from None
            time.sleep(0.1)
    reservations.release("status")
    supervisor.spawn("synthetic-publisher", [python, "-m", "morph_media_bridge", "run", "--config", str(media_dir / "bridge.json")], cwd=BRIDGE, env=env)
    status_token = (media_dir / "status.token").read_text().strip()
    first = supervisor.wait_json(ports["status"], "/api/media/v1/status", lambda data: data.get("state") == "streaming", token=status_token)
    count = first.get("counters", {}).get("encodedFramesReported", 0)
    supervisor.wait_json(ports["status"], "/api/media/v1/status", lambda data: data.get("counters", {}).get("encodedFramesReported", 0) > count, token=status_token)
    demo_env = {**env, "MORPH_DEMO_RUNTIME_DIR": str(records), "MORPH_DEMO_API_PORT": str(ports["api"]),
                "MORPH_DEMO_PORT": str(args.port), "MORPH_DEMO_ORIGIN": f"http://127.0.0.1:{ports['api']}",
                "MORPH_DEMO_TOKEN_FILE": str(token_file), "MORPH_DEMO_MODE": "1", "DISABLE_HMR": "true", "NODE_ENV": "development"}
    reservations.release("api")
    supervisor.spawn("simulation-records", [python, str(PACKAGE / "tools/run_local_demo.py"), "--backend"], cwd=STATION, env=demo_env)
    supervisor.wait_json(ports["api"], "/api/v1/schema", lambda data: data.get("capabilities", {}).get("dashboardRead", {}).get("version") == 1, token=token)
    reservations.release("dashboard")
    supervisor.spawn("dashboard", [node, str(DASHBOARD / "node_modules/tsx/dist/cli.mjs"), "tools/demoServer.ts"],
                     cwd=DASHBOARD, env={**demo_env, "MORPH_MEDIA_CONFIG_FILE": str(gateway)})
    supervisor.wait_json(args.port, "/api/local/v1/runtime", lambda data: data.get("runtimeMode") == "demo")
    report = check(args.port, "simulation", timeout=5, require_media=True)
    if not report["ok"]:
        raise LaunchError("Demo started but its records/media readiness check did not pass.")
    report["syntheticPublisherProgressObserved"] = True
    return report


def launch_station(args, supervisor: Supervisor, reservations: Reservations, runtime: Path, env: dict, node: str) -> dict:
    pairing = private_path(args.pairing_dir, directory=True)
    private_path(pairing / "connection.json", directory=False)
    if not (pairing / "morph-ca.pem").is_file():
        raise LaunchError("Explicit pairing directory is missing its existing CA certificate.")
    station_env = {**env, "PORT": str(args.port), "MORPH_CONTEXT_PAIRING_DIR": str(pairing),
                   "MORPH_STATION_ID": args.station_id, "MORPH_SKIP_DOTENV": "1",
                   "MORPH_DASHBOARD_RUNTIME_DIR": str(runtime), "NODE_ENV": "development", "DISABLE_HMR": "true"}
    if args.media_config:
        station_env["MORPH_MEDIA_CONFIG_FILE"] = str(private_path(args.media_config, directory=False))
    reservations.release("dashboard")
    supervisor.spawn("dashboard", [node, str(DASHBOARD / "node_modules/tsx/dist/cli.mjs"), "server.ts"], cwd=DASHBOARD, env=station_env)
    metadata = supervisor.wait_json(args.port, "/api/local/v1/runtime", lambda data: data.get("runtimeMode") == "station" and data.get("stationId") == args.station_id)
    return {"version": 1, "scope": "local-dashboard-startup", "runtimeMode": metadata["runtimeMode"],
            "recordsTransport": metadata["recordsTransport"], "remoteRecords": "not-probed-at-startup",
            "physicalAcceptance": "not-verified", "servicesStarted": ["dashboard"]}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="mode", required=True)
    for mode in ("demo", "station"):
        child = subparsers.add_parser(mode)
        child.add_argument("--port", type=int, default=3101 if mode == "demo" else 3000)
        child.add_argument("--node", help="Explicit Node executable; otherwise use the prepared runtime")
        child.add_argument("--duration", type=float, help="Stop this owned launch after this many ready seconds (QA)")
        child.add_argument("--report", type=Path, help="Write a new sanitized readiness/cleanup JSON report on exit")
        if mode == "demo":
            child.add_argument("--python", help="Python with the existing Station API and media bridge dependencies")
            child.add_argument("--ffmpeg", help="FFmpeg executable with libx264")
            child.add_argument("--mediamtx", help="MediaMTX v1.21.3 executable")
            child.add_argument("--fps", type=int, default=30, choices=range(1, 61), metavar="1..60")
        else:
            child.add_argument("--pairing-dir", type=Path, required=True)
            child.add_argument("--media-config", type=Path)
            child.add_argument("--station-id", default="intel-main")
    args = parser.parse_args(argv)
    if not 1 <= args.port <= 65535 or args.duration is not None and not 0 < args.duration <= 86400:
        parser.error("Choose a valid port and a duration greater than zero and at most 86400 seconds")
    if args.mode == "station" and not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.:-]{0,119}", args.station_id):
        parser.error("Choose a valid station identifier")
    if args.report and (args.report.exists() or not args.report.parent.is_dir()):
        parser.error("Report must be a new file in an existing directory")
    reservations, supervisor = Reservations(), None
    report = {"version": 1, "mode": args.mode, "dashboardPort": args.port, "ready": False}
    code = 1
    previous_signals = {}
    runtime_path = None
    try:
        reservations.reserve("dashboard", args.port)
        node = executable(args.node, "node", "node/bin/node")
        if not (DASHBOARD / "node_modules/tsx/dist/cli.mjs").is_file():
            raise LaunchError("Install the existing dashboard dependencies before launching.")
        supervisor = Supervisor()
        for sig in (signal.SIGINT, signal.SIGTERM):
            previous_signals[sig] = signal.signal(sig, lambda _sig, _frame: setattr(supervisor, "stopping", True))
        with tempfile.TemporaryDirectory(prefix="morph-owned-station-") as directory:
            runtime_path = Path(directory)
            try:
                env = environment(node)
                report["readiness"] = (launch_demo if args.mode == "demo" else launch_station)(args, supervisor, reservations, runtime_path, env, node)
                report["ready"] = True
                report["ownedPorts"] = dict(reservations.ports)
                print(f"Morph {args.mode} ready: http://127.0.0.1:{args.port}", flush=True)
                print("Synthetic records and changing synthetic video only." if args.mode == "demo" else "Mac dashboard only. Intel records/media readiness is checked separately.", flush=True)
                print("Ctrl+C stops only this launch and removes its disposable runtime.", flush=True)
                deadline = time.monotonic() + args.duration if args.duration else None
                while not supervisor.stopping and (deadline is None or time.monotonic() < deadline):
                    supervisor.healthy()
                    time.sleep(0.1)
                code = 0
            finally:
                report["cleanup"] = supervisor.close()
    except (LaunchError, OSError, ValueError, subprocess.SubprocessError) as error:
        interrupted = supervisor is not None and supervisor.stopping and str(error) == "Launch interrupted."
        code = 0 if interrupted else 1
        report["failure"] = "interrupted" if interrupted else str(error) if isinstance(error, LaunchError) else "Local launch configuration or dependency failed."
        print(report["failure"], file=sys.stderr)
    finally:
        reservations.close()
        for sig, previous in previous_signals.items():
            signal.signal(sig, previous)
        report["temporaryRuntimeRemoved"] = runtime_path is None or not runtime_path.exists()
        if report.get("cleanup", {}).get("ownedProcessesStopped") is False:
            code = 1
        report["exitCode"] = code
        if args.report:
            try:
                private_write(args.report, json.dumps(report, indent=2, allow_nan=False) + "\n")
            except OSError:
                print("Could not save the sanitized launch report.", file=sys.stderr)
                code = 1
    return code


if __name__ == "__main__":
    raise SystemExit(main())

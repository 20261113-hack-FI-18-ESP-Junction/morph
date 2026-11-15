#!/usr/bin/env python3
"""Operator-supervised three-pose teaching and replay for the identified follower.

This project tool uses installed LeRobot 0.7.0; it is not an upstream CLI.
Teaching never writes a goal. Replay is a separate explicit operation.
Replay is currently disabled after an operator-reported table collision.
"""

import argparse
import fcntl
import hashlib
import json
import os
from pathlib import Path
import signal
import stat
import subprocess
import sys
import termios
import time
from datetime import datetime, timezone
from importlib.metadata import version

from so101_three_point_core import (
    JOINTS, interpolate_pose, plan_waypoints, validate_calibration, validate_pose,
)

SERIAL = "5AE6075066"
CAL_ID = "2a1b5cc1-8e89-457e-8828-4d6d065f4ca6"
PORT = f"/dev/serial/by-id/usb-1a86_USB_Single_Serial_{SERIAL}-if00"
CALIBRATION = Path("/home/intel/project-morph/morph-robot/morph-robot-lerobot/.runtime/lerobot/calibration/robots/so_follower") / f"{CAL_ID}.json"
VOLTAGE_MIN, VOLTAGE_MAX, TEMPERATURE_MAX = 115, 122, 45
START_TOLERANCE, TRACKING_TOLERANCE, STABLE_TOLERANCE = 32, 32, 8
RAW_SPEED, RAW_ACCELERATION = 50, 1


def require_replay_clearance():
    """Keep replay disabled until a separate physical-path review changes the code.

    There is deliberately no command-line bypass. Joint position and speed
    bounds did not establish clearance from the table in replay-001.
    """
    raise ValueError(
        "Replay disabled after the operator-reported table collision on 2026-11-15. "
        "Do not replay the saved points. Physical inspection and a reviewed path "
        "with table clearance are required before this hold can be removed."
    )


def require(condition, message):
    if not condition:
        raise ValueError(message)


def utc_now():
    return datetime.now(timezone.utc).isoformat()


def read_json(path):
    raw = Path(path).read_bytes()
    require(len(raw) <= 2_000_000, "JSON exceeds the size limit.")

    def unique_pairs(pairs):
        result = {}
        for key, value in pairs:
            require(key not in result, f"Duplicate JSON key: {key}.")
            result[key] = value
        return result

    def reject_constant(value):
        raise ValueError(f"Nonfinite JSON value: {value}.")

    return json.loads(raw, object_pairs_hook=unique_pairs, parse_constant=reject_constant), hashlib.sha256(raw).hexdigest()


def save_new(path, data):
    with Path(path).open("x", encoding="utf-8") as stream:
        json.dump(data, stream, indent=2, allow_nan=False)
        stream.write("\n")


def load_teaching(path, calibration, digest):
    data, file_digest = read_json(path)
    require(type(data) is dict and type(data.get("schemaVersion")) is int
            and data["schemaVersion"] == 1, "Unsupported teaching record.")
    require(data.get("serial") == SERIAL and data.get("calibration_id") == CAL_ID,
            "Teaching record belongs to another robot.")
    require(data.get("calibration_sha256") == digest, "Calibration changed since teaching.")
    require(data.get("position_units") == "raw_encoder_counts", "Unexpected position units.")
    samples = data.get("samples")
    require(type(samples) is list and len(samples) == 3, "Exactly three captured samples are required.")
    points = []
    for sample in samples:
        require(type(sample) is dict, "Invalid sample.")
        stamp = datetime.fromisoformat(sample["captured_at"])
        require(stamp.tzinfo is not None, "Capture timestamps must include a timezone.")
        points.append(validate_pose(sample["positions"], calibration))
    return data, file_digest, points


def build_plan(points, calibration, segment_s=15.0, repeat=None, start_point=1):
    """Join reviewed segments; repeated rounds retrace them without a closing shortcut."""
    require(type(start_point) is int and start_point in (1, 3), "Start point must be 1 or 3.")
    require(repeat is None or (type(repeat) is int and 1 <= repeat <= 3),
            "Repeat must be between one and three supervised rounds.")
    ordered = list(points) if start_point == 1 else list(reversed(points))
    outbound = plan_waypoints(ordered, calibration, segment_s=segment_s)
    if repeat is None:
        outbound.update(start_point=start_point, route_point_numbers=[1, 2, 3] if start_point == 1 else [3, 2, 1],
                        repeat_rounds=None, end_pose=dict(outbound["frames"][-1]["positions"]))
        return outbound
    inbound = plan_waypoints(list(reversed(ordered)), calibration, segment_s=segment_s)
    frames = [{"offset_s": 0.0, "positions": dict(ordered[0])}]
    offset = 0.0
    for _ in range(repeat):
        for leg in (outbound, inbound):
            frames.extend({"offset_s": offset + f["offset_s"], "positions": dict(f["positions"])}
                          for f in leg["frames"][1:])
            offset += leg["duration_s"]
    sequence = [1, 2, 3, 2, 1] if start_point == 1 else [3, 2, 1, 2, 3]
    outbound.update(frames=frames, duration_s=offset, repeat_rounds=repeat, start_point=start_point,
                    route_point_numbers=[sequence[0]] + sequence[1:] * repeat,
                    repeated_segments_only=True, return_to_start_included=True,
                    end_pose=dict(ordered[0]))
    return outbound


class Journal:
    def __init__(self, path, mode):
        self.stream = Path(path).open("x", encoding="utf-8")
        script = Path(__file__).resolve()
        sources = {str(p): hashlib.sha256(p.read_bytes()).hexdigest()
                   for p in (script, script.with_name("so101_three_point_core.py"))}
        self.emit("start", mode=mode, serial=SERIAL, hardware_verified=False,
                  argv=sys.argv, source_sha256=sources, python=sys.executable)

    def emit(self, kind, **fields):
        self.stream.write(json.dumps({"at": utc_now(), "kind": kind, **fields}, allow_nan=False) + "\n")
        self.stream.flush()


def resolve_port():
    from serial.tools.list_ports import comports

    path = Path(PORT).resolve(strict=True)
    require(stat.S_ISCHR(path.stat().st_mode), "Follower port is not a character device.")
    matches = [p for p in comports() if p.serial_number == SERIAL]
    require(len(matches) == 1 and Path(matches[0].device).resolve() == path,
            "USB identity is absent or ambiguous.")
    result = subprocess.run(["fuser", str(path)], capture_output=True, text=True, timeout=3)
    require(result.returncode == 1 and not result.stdout.strip() and not result.stderr.strip(),
            "Follower port is occupied or ownership cannot be verified. Close its owner normally.")
    return path


def make_bus(path):
    require(version("lerobot") == "0.7.0" and version("rustypot") == "1.13.1",
            "Installed dependencies differ from the reviewed LeRobot 0.7.0 / rustypot 1.13.1.")
    from lerobot.motors import Motor, MotorNormMode, SerialMotorsBus

    motors = {name: Motor(i, "sts3215", MotorNormMode.RANGE_0_100 if name == "gripper"
                          else MotorNormMode.RANGE_M100_100) for i, name in enumerate(JOINTS, 1)}
    bus = SerialMotorsBus(port=str(path), motors=motors)
    require(bus.default_baudrate == 1_000_000 and bus.default_timeout == 50,
            "Unexpected serial baud rate or timeout.")
    return bus


class Follower:
    def __init__(self, bus, calibration, journal):
        self.bus, self.calibration, self.journal = bus, calibration, journal
        self.writes_started = False
        self.original_ram = {}
        self.goals = {}

    def open(self):
        path = Path(self.bus.port)
        identity = lambda info: (info.st_dev, info.st_ino, info.st_rdev)
        expected = identity(path.stat())
        self.bus.connect(handshake=False)
        descriptors = []
        for item in Path("/proc/self/fd").iterdir():
            try:
                info = os.fstat(int(item.name))
                if stat.S_ISCHR(info.st_mode) and info.st_rdev == expected[2]:
                    descriptors.append(int(item.name))
            except OSError:
                continue
        require(len(descriptors) == 1 and identity(path.stat()) == expected,
                "Could not identify one unchanged serial descriptor.")
        require(identity(os.fstat(descriptors[0])) == expected, "Serial descriptor changed during open.")
        fcntl.ioctl(descriptors[0], termios.TIOCEXCL)
        require(identity(path.stat()) == expected, "Serial device changed during exclusive claim.")
        owners = subprocess.run(["fuser", str(path)], capture_output=True, text=True, timeout=3)
        require(owners.returncode == 0 and owners.stdout.split() == [str(os.getpid())],
                "Another process acquired the serial port; no motor writes allowed.")
        self.journal.emit("port_open", port=str(path), exclusive=True)

    def read(self, register, joint):
        value = self.bus.read(register, joint, normalize=False, num_retry=0)
        require(type(value) is int, f"Invalid raw {joint}/{register}.")
        return value

    def frame(self, expected_torque=None, goals=None):
        began = time.monotonic()
        registers = ("Present_Position", "Status", "Torque_Enable", "Present_Voltage", "Present_Temperature")
        rows = {j: {r: self.read(r, j) for r in registers} for j in JOINTS}
        self.journal.emit("telemetry", motors=rows, duration_s=time.monotonic() - began)
        require(time.monotonic() - began < 0.5, "Telemetry is stale; stopping.")
        for joint, row in rows.items():
            require(row["Status"] == 0, f"{joint}: hardware status {row['Status']}; stopping.")
            require(VOLTAGE_MIN <= row["Present_Voltage"] <= VOLTAGE_MAX,
                    f"{joint}: voltage outside the retained 11.5–12.2 V diagnostic guard.")
            require(0 <= row["Present_Temperature"] < TEMPERATURE_MAX,
                    f"{joint}: temperature outside the retained <45 C guard.")
            if expected_torque is not None:
                require(row["Torque_Enable"] == expected_torque[joint], f"{joint}: unexpected torque state.")
            if goals is not None and joint in goals:
                require(abs(row["Present_Position"] - goals[joint]) <= TRACKING_TOLERANCE,
                        f"{joint}: tracking error exceeds {TRACKING_TOLERANCE} counts.")
        positions = {j: rows[j]["Present_Position"] for j in JOINTS}
        # Teaching may approach a mechanical limit; saving/planning applies the 32-count margin.
        validate_pose(positions, self.calibration, margin=0)
        return positions

    def preflight(self):
        for joint in JOINTS:
            cal = self.calibration[joint]
            expected = {"Model_Number": 777, "Operating_Mode": 0, "Phase": 12,
                        "Angular_Resolution": 1, "Homing_Offset": cal["homing_offset"],
                        "Min_Position_Limit": cal["range_min"], "Max_Position_Limit": cal["range_max"]}
            actual = {key: self.read(key, joint) for key in expected}
            self.journal.emit("configuration_read", joint=joint, registers=actual)
            require(actual == expected, f"{joint}: hardware configuration/calibration differs; no automatic repair.")
        self.frame()

    def write(self, register, joint, value):
        allowed = ((register == "Torque_Enable" and value == 0)
                   or (register == "Goal_Position" and joint in self.goals and value == self.goals[joint])
                   or (register == "Goal_Velocity" and value == RAW_SPEED)
                   or (register == "Acceleration" and value == RAW_ACCELERATION))
        require(allowed and joint in JOINTS and type(value) is int, "Register write is outside the reviewed RAM allowlist.")
        self.writes_started = True  # A lost acknowledgment may follow an actual write.
        self.journal.emit("write_attempt", register=register, joint=joint, value=value)
        self.bus.write(register, joint, value, normalize=False, num_retry=0)

    def release(self):
        for joint in JOINTS:
            self.write("Torque_Enable", joint, 0)
        return self.frame(expected_torque={j: 0 for j in JOINTS})

    def stable_pose(self):
        frames = []
        for _ in range(3):
            frames.append(self.frame(expected_torque={j: 0 for j in JOINTS}))
            time.sleep(0.1)
        require(all(max(p[j] for p in frames) - min(p[j] for p in frames) <= STABLE_TOLERANCE for j in JOINTS),
                "Arm is still moving; no point was accepted.")
        return validate_pose(frames[-1], self.calibration)

    def prepare_hold(self, start):
        for joint in JOINTS:
            self.original_ram[joint] = {r: self.read(r, joint) for r in ("Goal_Velocity", "Acceleration")}
            for register, value in (("Goal_Velocity", RAW_SPEED), ("Acceleration", RAW_ACCELERATION)):
                self.write(register, joint, value)
                require(self.read(register, joint) == value, f"{joint}: RAM limit did not read back.")
        self.frame(expected_torque={j: 0 for j in JOINTS})
        for joint in JOINTS:
            current = self.read("Present_Position", joint)
            require(abs(current - start[joint]) <= STABLE_TOLERANCE, "Arm moved before hold; stopping.")
            self.goals[joint] = current
            # On the inspected STS firmware even this same-position goal can energize the servo.
            self.write("Goal_Position", joint, current)
            require(self.read("Goal_Position", joint) == current, f"{joint}: hold goal readback mismatch.")
            self.frame(expected_torque={j: int(j in self.goals) for j in JOINTS}, goals=self.goals)

    def send_pose(self, pose):
        validate_pose(pose, self.calibration)
        require(all(abs(pose[j] - self.goals[j]) <= 8 for j in JOINTS), "Command step exceeds eight raw counts.")
        self.frame(expected_torque={j: 1 for j in JOINTS}, goals=self.goals)
        self.goals = dict(pose)
        for joint in JOINTS:
            self.write("Goal_Position", joint, pose[joint])
            require(self.read("Goal_Position", joint) == pose[joint], f"{joint}: goal readback mismatch.")

    def settle(self, pose):
        deadline = time.monotonic() + 3
        while True:
            positions = self.frame(expected_torque={j: 1 for j in JOINTS}, goals=pose)
            if all(abs(positions[j] - pose[j]) <= STABLE_TOLERANCE for j in JOINTS):
                return positions
            require(time.monotonic() < deadline, "Final point did not converge; stopping.")
            time.sleep(0.1)

    def cleanup(self):
        failures, off = [], {}
        if self.writes_started:
            # Try every off write before spending time on readbacks. No stale goal is restored.
            for joint in JOINTS:
                try:
                    self.bus.write("Torque_Enable", joint, 0, normalize=False, num_retry=0)
                except BaseException as exc:
                    failures.append(f"{joint} torque-off write: {exc}")
            for joint in JOINTS:
                try:
                    off[joint] = self.read("Torque_Enable", joint) == 0
                except BaseException as exc:
                    failures.append(f"{joint} torque-off read: {exc}")
            if all(off.get(j) for j in JOINTS):
                for joint, settings in self.original_ram.items():
                    for register, value in settings.items():
                        try:
                            self.bus.write(register, joint, value, normalize=False, num_retry=0)
                            require(self.read(register, joint) == value, "RAM restoration mismatch.")
                        except BaseException as exc:
                            failures.append(f"{joint}/{register} restore: {exc}")
                for joint in JOINTS:
                    try:
                        off[joint] = self.read("Torque_Enable", joint) == 0
                        if not off[joint]:
                            self.bus.write("Torque_Enable", joint, 0, normalize=False, num_retry=0)
                            off[joint] = self.read("Torque_Enable", joint) == 0
                            failures.append(f"{joint}: torque changed during RAM restoration.")
                    except BaseException as exc:
                        off[joint] = False
                        failures.append(f"{joint} final torque verification: {exc}")
        try:
            self.bus.disconnect(disable_torque=False)
        except BaseException as exc:
            failures.append(f"Port close: {exc}")
        complete = not failures and (not self.writes_started or all(off.get(j) for j in JOINTS))
        self.journal.emit("cleanup", completed=complete, torque_off=off, errors=failures)
        if not complete:
            print("CLEANUP UNVERIFIED. Keep the arm supported and remove motor power.", flush=True)
        return complete


def teach(follower, output, calibration, digest, segment_s=15.0):
    follower.release()
    print("Torque is OFF. Keep the arm supported. Move it by hand; do not rotate the wrist fully.", flush=True)
    samples = []
    for number in range(1, 4):
        input(f"Place the follower at point {number}, hold it still, then press Enter: ")
        require(hashlib.sha256(CALIBRATION.read_bytes()).hexdigest() == digest,
                "Calibration changed during teaching; no new point accepted.")
        pose = follower.stable_pose()
        samples.append({"captured_at": utc_now(), "positions": pose})
        print(f"Captured point {number}: {json.dumps(pose)}", flush=True)
        follower.journal.emit("point_captured", number=number, sample=samples[-1])
    data = {"schemaVersion": 1, "serial": SERIAL, "calibration_id": CAL_ID,
            "calibration_sha256": digest, "position_units": "raw_encoder_counts",
            "samples": samples, "physical_replay_verified": False}
    require(hashlib.sha256(CALIBRATION.read_bytes()).hexdigest() == digest,
            "Calibration changed during teaching; no trajectory saved.")
    save_new(output, data)
    print(f"Three points saved to {output}. No replay has started.", flush=True)
    # Keep acquired points even when the proposed path is too fast or otherwise inadmissible.
    plan_waypoints([s["positions"] for s in samples], calibration, segment_s=segment_s)
    print("For later replay, return by hand close to point 1. Each joint must be within 32 counts.", flush=True)
    while True:
        answer = input("Press Enter to check alignment with point 1, or type done to finish teaching: ").strip().lower()
        if answer == "done":
            break
        position = follower.stable_pose()
        delta = {j: position[j] - samples[0]["positions"][j] for j in JOINTS}
        print("Point 1 alignment, raw counts: " + json.dumps(delta), flush=True)
        if all(abs(v) <= START_TOLERANCE for v in delta.values()):
            print("Near point 1. Teaching finished; replay still requires its separate command.", flush=True)
            break


def replay(follower, plan, calibration, digest):
    require_replay_clearance()
    current_digest = hashlib.sha256(CALIBRATION.read_bytes()).hexdigest()
    require(current_digest == digest, "Calibration changed during preparation.")
    start = follower.stable_pose()  # Must already be torque-off; no automatic release during replay.
    first = plan["frames"][0]["positions"]
    require(all(abs(start[j] - first[j]) <= START_TOLERANCE for j in JOINTS),
            "Manually return near the selected start point with torque off. No automatic approach from a distant pose.")
    follower.prepare_hold(start)
    held = dict(follower.goals)
    require(all(abs(held[j] - first[j]) <= START_TOLERANCE for j in JOINTS),
            "Held position moved outside the nearby-start allowance.")
    approach = [interpolate_pose(held, first, i / 10) for i in range(1, 11)]
    # At most 32 counts over one second, then the reviewed route. No catch-up bursts.
    frames = [(i / 10, p) for i, p in enumerate(approach, 1)]
    frames.extend((1 + f["offset_s"], f["positions"]) for f in plan["frames"][1:])
    began = last = time.monotonic()
    previous_offset = 0.0
    for offset, pose in frames:
        interval = offset - previous_offset
        time.sleep(max(0.0, interval - (time.monotonic() - last)))
        now = time.monotonic()
        require(now - last <= max(0.5, interval * 3), "Control loop stalled; no catch-up movement allowed.")
        require(hashlib.sha256(CALIBRATION.read_bytes()).hexdigest() == digest, "Calibration changed during replay.")
        follower.send_pose(pose)
        last = time.monotonic()
        previous_offset = offset
    final = follower.settle(plan["frames"][-1]["positions"])
    follower.journal.emit("commanded_path_completed", final_position=final,
                          actual_path_seconds=time.monotonic() - began,
                          nominal_path_seconds=1 + plan["duration_s"], operator_observation="pending")
    print("Recorded route finished. Operator confirmation of physical movement is still required.", flush=True)


def align(follower, first):
    """Read positions only; never enable, disable or command a motor."""
    print("Alignment only: no motor writes. Keep the torque-off arm supported.", flush=True)
    while True:
        position = follower.stable_pose()
        delta = {j: position[j] - first[j] for j in JOINTS}
        print("Difference from point 1, raw counts: " + json.dumps(delta), flush=True)
        follower.journal.emit("alignment", positions=position, target=first, delta=delta)
        if all(abs(v) <= START_TOLERANCE for v in delta.values()):
            print("Near point 1. Alignment verified; replay has not started.", flush=True)
            return
        answer = input("Move by hand toward point 1, then Enter to check; type stop to close: ").strip().lower()
        if answer == "stop":
            raise InterruptedError("Operator stopped alignment.")


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=("teach", "plan", "align", "replay"))
    parser.add_argument("--input", type=Path)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--journal", type=Path)
    parser.add_argument("--segment-s", type=float, default=15.0,
                        help="Seconds per taught segment, 15–60; speed and step limits stay unchanged.")
    parser.add_argument("--repeat", type=int, choices=(1, 2, 3),
                        help="Supervised out-and-back rounds over the same segments; no direct closing shortcut.")
    parser.add_argument("--start-point", type=int, choices=(1, 3), default=1)
    parser.add_argument("--operator-ready", action="store_true",
                        help="Operator is present with support, clear path and physical motor-power cutoff.")
    args = parser.parse_args(argv)
    if args.mode == "replay":
        try:
            require_replay_clearance()
        except ValueError as exc:
            print(f"STOPPED: {exc}", flush=True)
            return 1
    require(15 <= args.segment_s <= 60, "Segment duration must be finite and between 15 and 60 seconds.")
    calibration, digest = read_json(CALIBRATION)
    calibration = validate_calibration(calibration)
    plan = None
    if args.mode != "teach":
        require(args.input is not None, "This mode requires --input.")
        _, input_digest, points = load_teaching(args.input, calibration, digest)
        if args.mode != "align":
            plan = build_plan(points, calibration, segment_s=args.segment_s,
                              repeat=args.repeat, start_point=args.start_point)
            plan.update(calibration_sha256=digest, teaching_sha256=input_digest)
        if args.mode == "plan":
            if args.output:
                save_new(args.output, plan)
            print(json.dumps({k: v for k, v in plan.items() if k != "frames"}, indent=2))
            return 0
    require(args.operator_ready, "Physical access requires --operator-ready after explicit operator confirmation.")
    require(args.journal is not None, "Physical operations require a new --journal path.")
    if args.mode == "teach":
        require(args.output is not None and not args.output.exists(), "Teaching requires a new --output path.")
    journal = Journal(args.journal, args.mode)
    follower = None
    previous_handlers = {}
    outcome = "aborted"
    cleanup_ok = True

    def interrupt(number, _frame):
        raise InterruptedError(f"Signal {number}; stopping and releasing torque.")

    try:
        for number in (signal.SIGINT, signal.SIGTERM, signal.SIGHUP, signal.SIGALRM):
            previous_handlers[number] = signal.signal(number, interrupt)
        deadline = 600 if args.mode in ("teach", "align") else 1.5 * (plan["duration_s"] + 1) + 15
        signal.setitimer(signal.ITIMER_REAL, deadline)
        path = resolve_port()
        follower = Follower(make_bus(path), calibration, journal)
        follower.open()
        follower.preflight()
        if args.mode == "teach":
            teach(follower, args.output, calibration, digest, segment_s=args.segment_s)
        elif args.mode == "align":
            align(follower, points[0])
        else:
            replay(follower, plan, calibration, digest)
        outcome = {"teach": "teaching_saved", "align": "alignment_verified_no_writes",
                   "replay": "commanded_replay_completed_observation_pending"}[args.mode]
    except (Exception, KeyboardInterrupt) as exc:
        journal.emit("aborted", error=f"{type(exc).__name__}: {exc}")
        print(f"STOPPED: {type(exc).__name__}: {exc}", flush=True)
    finally:
        signal.setitimer(signal.ITIMER_REAL, 0)
        for number in previous_handlers:
            signal.signal(number, signal.SIG_IGN)
        try:
            if follower:
                cleanup_ok = follower.cleanup()
            journal.emit("finish", outcome=outcome, cleanup_verified=cleanup_ok)
        finally:
            journal.stream.close()
            for number, handler in previous_handlers.items():
                signal.signal(number, handler)
    return 0 if outcome != "aborted" and cleanup_ok else 1


if __name__ == "__main__":
    sys.exit(main())

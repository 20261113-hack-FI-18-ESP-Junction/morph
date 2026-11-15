#!/usr/bin/env python3
"""Inspect SO-101 motor registers without torque or configuration writes."""

import argparse
from datetime import datetime, timezone
from importlib import metadata
import json
import os
import re
import signal
import stat
import sys
import time


MOTOR_NAMES = (
    "shoulder_pan", "shoulder_lift", "elbow_flex",
    "wrist_flex", "wrist_roll", "gripper",
)
REGISTERS = ("Model_Number", "ID", "Present_Position", "Torque_Enable", "Present_Voltage")
EXPECTED_MODEL = 777
INITIAL_BAUDRATE = 1_000_000
DISCOVERY_BAUDRATES = (1_000_000, 500_000, 250_000, 128_000, 115_200, 57_600, 38_400, 19_200)
DISCOVERY_SETTLE_SECONDS = 1
AUDITED_SDK_MAX_ID = 252


class ProbeTimeout(TimeoutError):
    pass


def deadline_expired(signum, frame):
    raise ProbeTimeout("Probe deadline exceeded")


def read_motors(bus, report, direct_read=False):
    """The only bus operations here are ping and register reads."""
    for expected_id, name in enumerate(MOTOR_NAMES, 1):
        motor = {"name": name, "expected_id": expected_id, "registers": {}, "errors": []}
        report["motors"].append(motor)
        if not direct_read:
            try:
                motor["ping_model"] = bus.ping(expected_id, num_retry=0, raise_on_error=True)
            except ProbeTimeout:
                raise
            except Exception as exc:
                motor["errors"].append({"operation": "ping", "error": str(exc)})
                continue
            if motor["ping_model"] != EXPECTED_MODEL:
                motor["errors"].append({
                    "operation": "ping", "error": "Unexpected model; register reads skipped.",
                    "expected_model": EXPECTED_MODEL,
                })
                continue

        for register in (("Model_Number", "Present_Voltage") if direct_read else REGISTERS):
            try:
                value = bus.read(register, name, normalize=False, num_retry=0)
                motor["registers"][register] = value
            except ProbeTimeout:
                raise
            except Exception as exc:
                motor["errors"].append({"operation": f"read {register}", "error": str(exc)})

        readings = motor["registers"]
        for register, expected in (("Model_Number", EXPECTED_MODEL), ("ID", expected_id)):
            if register in readings and readings[register] != expected:
                motor["errors"].append({"operation": f"validate {register}", "expected": expected,
                                        "observed": readings[register]})
        if "Present_Voltage" in readings:
            motor["voltage_v"] = round(readings["Present_Voltage"] * 0.1, 3)


def broadcast_receive_timeout_ms(baudrate):
    """LeRobot 0.6.0 _broadcast_ping receive window; model reads take extra time."""
    return 6 * AUDITED_SDK_MAX_ID * (10_000 / baudrate) + 3 * AUDITED_SDK_MAX_ID + 16


def discover_motors(bus, report):
    """Change host baud only, then broadcast PING and read responders' models."""
    discovery = report["discovery"]
    if bus.protocol_version != 0:
        raise RuntimeError("Discovery requires the audited Feetech protocol 0 implementation.")
    if set(bus.model_baudrate_table["sts3215"]) != set(DISCOVERY_BAUDRATES):
        raise RuntimeError("Installed STS3215 baud table differs from the audited table.")
    for baudrate in DISCOVERY_BAUDRATES:
        attempt = {"baudrate": baudrate, "responders": [], "status": "pending", "errors": [],
                   "sdk_broadcast_receive_timeout_ms": round(broadcast_receive_timeout_ms(baudrate), 3)}
        discovery["attempts"].append(attempt)
        attempt_start = time.monotonic()
        try:
            # The installed SDK reopens pyserial when the host baud changes.
            bus.set_baudrate(baudrate)
            if bus.get_baudrate() != baudrate:
                raise RuntimeError("Host baud did not match the requested rate; no PING was sent.")
            time.sleep(DISCOVERY_SETTLE_SECONDS)
            attempt["status"] = "probing"
            # This API sends broadcast PING, then READs model numbers only for
            # responding IDs. Do not add setup, configuration, or torque calls.
            models = bus.broadcast_ping(num_retry=0, raise_on_error=True)
            attempt["responders"] = [
                {"id": motor_id, "model_number": model, "matches_sts3215": model == EXPECTED_MODEL}
                for motor_id, model in sorted((models or {}).items())
            ]
            attempt["status"] = "responses" if attempt["responders"] else "no_valid_response"
        except (ProbeTimeout, KeyboardInterrupt):
            attempt["status"] = "interrupted"
            raise
        except Exception as exc:
            phase = "broadcast_ping_and_model_reads" if attempt["status"] == "probing" else "host_baud_and_settle"
            attempt["status"] = (
                "no_valid_response" if phase == "broadcast_ping_and_model_reads" and isinstance(exc, ConnectionError)
                else "error"
            )
            attempt["errors"].append({"operation": phase, "type": type(exc).__name__, "error": str(exc)})
        finally:
            attempt["elapsed_seconds"] = round(time.monotonic() - attempt_start, 3)
    discovery["scan_complete"] = all(
        attempt["status"] in ("responses", "no_valid_response") for attempt in discovery["attempts"]
    )


def close_bus(bus, report):
    """Explicitly preserve the motor torque state when closing the serial port."""
    if bus is None:
        report["cleanup"] = "Bus was not constructed."
        return
    try:
        if bus.is_connected:
            bus.disconnect(disable_torque=False)
            report["cleanup"] = "Serial port closed with disable_torque=False."
        else:
            report["cleanup"] = "Serial port was not open."
    except (Exception, KeyboardInterrupt) as exc:
        report["errors"].append({"operation": "close", "error": str(exc) or type(exc).__name__})
        report["cleanup"] = "Failed to confirm that the serial port closed."


def timeout_seconds(value):
    value = float(value)
    if not 1 <= value <= 60:
        raise argparse.ArgumentTypeError("timeout must be between 1 and 60 seconds")
    return value


def main():
    parser = argparse.ArgumentParser(
        description="Read SO-101 motor IDs 1–6 using the audited LeRobot 0.6.0 bus API. "
                    "Optional --discover searches other IDs at the eight supported STS3215 host baud rates. "
                    "No torque, target-position, calibration, or configuration registers are written. "
                    "Opening a serial port can affect DTR/RTS. Ensure no other process is using "
                    "the same port. Run in the existing Studio Python environment.",
    )
    parser.add_argument("--port", required=True, help="explicit /dev/ttyACM*, /dev/ttyUSB*, or /dev/serial/* path")
    parser.add_argument("--timeout", type=timeout_seconds, default=20,
                        help="overall probe deadline in seconds, 1–60 (default: 20); cleanup gets up to 2 more seconds")
    modes = parser.add_mutually_exclusive_group()
    modes.add_argument("--direct-read", action="store_true",
                       help="wait 1 second after opening, then read model and voltage without requiring a successful ping")
    modes.add_argument("--discover", action="store_true",
                       help="broadcast PING and model READ at eight host baud rates; no motor setup or calibration")
    args = parser.parse_args()
    started = time.monotonic()
    report = {
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "port": args.port,
        "scope": "PING and READ only; no motor-register writes. Serial open/close may affect DTR/RTS.",
        "baudrate": None if args.discover else INITIAL_BAUDRATE,
        "protocol_version": 0,
        "expected_model": EXPECTED_MODEL,
        "timeout_seconds": args.timeout,
        "mode": "discovery" if args.discover else ("direct_read" if args.direct_read else "ping_then_read"),
        "settle_seconds": DISCOVERY_SETTLE_SECONDS if args.discover else (1 if args.direct_read else 0),
        "motors": [],
        "errors": [],
    }
    if args.discover:
        report["initial_host_baudrate"] = INITIAL_BAUDRATE
        report["discovery"] = {
            "baudrates": list(DISCOVERY_BAUDRATES), "attempts": [], "scan_complete": False,
            "motor_chain_complete": None, "calibration_verified": False,
            "notes": [
                "Only host serial settings change; each baud switch may reopen the port and affect DTR/RTS.",
                "Broadcast PING is followed by model-register READs for responding IDs only.",
                "Receive-window estimates exclude settling, model reads, and overhead; the overall probe deadline still applies.",
                "No valid response does not distinguish wrong configuration, duplicate-ID collisions, or controller/wiring problems.",
                "Responses identify observed ID/model pairs, not the number of physical motors, chain completeness, or calibration.",
            ],
        }
    bus = None
    previous_handler = signal.signal(signal.SIGALRM, deadline_expired)
    signal.setitimer(signal.ITIMER_REAL, args.timeout)
    try:
        resolved = os.path.realpath(args.port)
        report["resolved_port"] = resolved
        if not os.path.isabs(args.port) or not re.fullmatch(r"/dev/tty(?:ACM|USB)\d+", resolved):
            raise ValueError("Port must resolve to an explicit /dev/ttyACM<number> or /dev/ttyUSB<number>.")
        if not stat.S_ISCHR(os.stat(resolved).st_mode):
            raise ValueError("Requested port is not a character device.")
        report["lerobot_version"] = metadata.version("lerobot")
        if report["lerobot_version"] != "0.6.0":
            raise RuntimeError("This probe was audited for LeRobot 0.6.0; review other versions before use.")
        if args.discover:
            report["feetech_sdk_version"] = metadata.version("feetech-servo-sdk")
            if report["feetech_sdk_version"] != "1.0.0":
                raise RuntimeError("Discovery was audited for feetech-servo-sdk 1.0.0; review other versions before use.")
            import scservo_sdk as scs
            if (scs.MAX_ID, scs.BROADCAST_ID, scs.INST_PING, scs.INST_READ) != (AUDITED_SDK_MAX_ID, 254, 1, 2):
                raise RuntimeError("SDK protocol constants differ from the audited discovery implementation.")

        # Delayed imports keep --help usable without LeRobot installed.
        from lerobot.motors.feetech.feetech import FeetechMotorsBus
        from lerobot.motors.motors_bus import Motor, MotorNormMode

        motors = {
            name: Motor(
                id=identifier, model="sts3215",
                norm_mode=MotorNormMode.RANGE_0_100 if name == "gripper" else MotorNormMode.RANGE_M100_100,
            )
            for identifier, name in enumerate(MOTOR_NAMES, 1)
        }
        bus = FeetechMotorsBus(port=resolved, motors=motors, protocol_version=0)
        bus.connect(handshake=False)
        if bus.get_baudrate() != INITIAL_BAUDRATE:
            raise RuntimeError("Unexpected host baudrate; probe stopped without changing it.")
        if args.discover:
            discover_motors(bus, report)
        elif args.direct_read:
            time.sleep(1)
            read_motors(bus, report, direct_read=True)
        else:
            read_motors(bus, report)
    except (Exception, KeyboardInterrupt) as exc:
        report["errors"].append({"operation": "probe", "type": type(exc).__name__,
                                  "error": str(exc) or type(exc).__name__})
    finally:
        signal.setitimer(signal.ITIMER_REAL, 2)
        try:
            close_bus(bus, report)
        finally:
            signal.setitimer(signal.ITIMER_REAL, 0)
            signal.signal(signal.SIGALRM, previous_handler)

    report["elapsed_seconds"] = round(time.monotonic() - started, 3)
    if args.discover:
        discovery = report["discovery"]
        discovery["sts3215_response_found"] = any(
            motor["matches_sts3215"] for attempt in discovery["attempts"] for motor in attempt["responders"]
        )
        report["ok"] = not report["errors"] and discovery["scan_complete"] and discovery["sts3215_response_found"]
        report["ok_meaning"] = "Discovery completed and at least one STS3215 model responded; this does not verify a complete arm."
    else:
        report["ok"] = (
            not report["errors"] and len(report["motors"]) == len(MOTOR_NAMES)
            and all(not motor["errors"] and len(motor["registers"]) == (2 if args.direct_read else len(REGISTERS))
                    for motor in report["motors"])
        )
    print(json.dumps(report, indent=2, ensure_ascii=False))
    return 0 if report["ok"] else 2


if __name__ == "__main__":
    sys.exit(main())

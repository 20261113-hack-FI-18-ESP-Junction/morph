"""Exercise motor discovery and cleanup with a bus that forbids motor writes."""

from contextlib import ExitStack, redirect_stdout
import importlib.util
import io
import json
from pathlib import Path
import signal
import stat
import sys
from types import ModuleType, SimpleNamespace
import unittest
from unittest.mock import call, patch


SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "probe_so101_readonly.py"
SPEC = importlib.util.spec_from_file_location("motor_probe_under_test", SCRIPT)
probe = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(probe)


class ReadOnlyBus:
    protocol_version = 0
    model_baudrate_table = {"sts3215": dict.fromkeys(probe.DISCOVERY_BAUDRATES)}

    def __init__(self, responses=None, baud_failure=None, discovery_only=True, stop_failure=False):
        self.responses = responses or {}
        self.baud_failure = baud_failure
        self.discovery_only = discovery_only
        self.stop_failure = stop_failure
        self.is_connected = False
        self.baudrate = probe.INITIAL_BAUDRATE
        self.settled = False
        self.events = []

    def __getattr__(self, name):
        raise AssertionError(f"Unreviewed operation, including any write/torque/setup call: {name}")

    def connect(self, *, handshake):
        assert handshake is False, "Discovery must not run a configuring handshake"
        self.events.append(("connect", handshake))
        self.is_connected = True

    def get_baudrate(self):
        return self.baudrate

    def set_baudrate(self, baudrate):
        assert baudrate in probe.DISCOVERY_BAUDRATES
        self.events.append(("host_baud", baudrate))
        self.settled = False
        if baudrate == self.baud_failure:
            raise RuntimeError("Simulated host baud failure")
        self.baudrate = baudrate

    def sleep(self, seconds):
        assert seconds >= 1, "Every open/reopen needs at least one second to settle"
        self.events.append(("settle", seconds))
        self.settled = True

    def broadcast_ping(self, *, num_retry, raise_on_error):
        assert self.is_connected and self.settled
        assert num_retry == 0 and raise_on_error is True
        self.events.append(("broadcast_ping_and_model_reads", self.baudrate))
        response = self.responses.get(self.baudrate)
        if isinstance(response, BaseException):
            raise response
        if response is None:
            raise ConnectionError("[TxRxResult] There is no status packet!")
        return response

    def ping(self, motor_id, *, num_retry, raise_on_error):
        assert not self.discovery_only, "Discovery must not use the fixed-ID probe"
        assert num_retry == 0 and raise_on_error is True
        self.events.append(("ping", motor_id))
        return probe.EXPECTED_MODEL

    def read(self, register, name, *, normalize, num_retry):
        assert not self.discovery_only, "Discovery must use only the broadcast API's model reads"
        assert normalize is False and num_retry == 0
        assert register in probe.REGISTERS
        self.events.append(("read", register, name))
        return {"Model_Number": probe.EXPECTED_MODEL, "ID": probe.MOTOR_NAMES.index(name) + 1,
                "Present_Position": 2048, "Torque_Enable": 0, "Present_Voltage": 120}[register]

    def disconnect(self, *, disable_torque):
        assert disable_torque is False, "Closing must not disable torque or write registers"
        self.events.append(("disconnect", disable_torque))
        if self.stop_failure:
            raise OSError("Simulated close failure")
        self.is_connected = False


def fake_modules(bus):
    names = ("lerobot", "lerobot.motors", "lerobot.motors.feetech",
             "lerobot.motors.feetech.feetech", "lerobot.motors.motors_bus", "scservo_sdk")
    modules = {name: ModuleType(name) for name in names}

    def construct(*, port, motors, protocol_version):
        assert port == "/dev/ttyACM999" and protocol_version == 0
        assert set(motors) == set(probe.MOTOR_NAMES)
        return bus

    modules["lerobot.motors.feetech.feetech"].FeetechMotorsBus = construct
    modules["lerobot.motors.motors_bus"].Motor = SimpleNamespace
    modules["lerobot.motors.motors_bus"].MotorNormMode = SimpleNamespace(RANGE_0_100=0, RANGE_M100_100=1)
    for name, value in {"MAX_ID": 252, "BROADCAST_ID": 254, "INST_PING": 1, "INST_READ": 2}.items():
        setattr(modules["scservo_sdk"], name, value)
    return modules


class MotorDiscoveryTests(unittest.TestCase):
    def invoke(self, bus, flags=("--discover",), sleep_error=None):
        output = io.StringIO()
        versions = {"lerobot": "0.6.0", "feetech-servo-sdk": "1.0.0"}
        with ExitStack() as stack:
            stack.enter_context(patch.dict(sys.modules, fake_modules(bus)))
            stack.enter_context(patch.object(sys, "argv", [str(SCRIPT), "--port", "/dev/ttyACM999", *flags]))
            stack.enter_context(patch.object(probe.os.path, "realpath", return_value="/dev/ttyACM999"))
            stack.enter_context(patch.object(probe.os, "stat", return_value=SimpleNamespace(st_mode=stat.S_IFCHR)))
            stack.enter_context(patch.object(probe.metadata, "version", side_effect=versions.__getitem__))
            stack.enter_context(patch.object(probe.signal, "signal", return_value=signal.SIG_DFL))
            timer = stack.enter_context(patch.object(probe.signal, "setitimer"))
            stack.enter_context(patch.object(probe.time, "sleep", side_effect=sleep_error or bus.sleep))
            stack.enter_context(redirect_stdout(output))
            code = probe.main()
        self.assertEqual(timer.call_args_list, [call(signal.ITIMER_REAL, 20), call(signal.ITIMER_REAL, 2),
                                                call(signal.ITIMER_REAL, 0)])
        return code, json.loads(output.getvalue())

    def assert_closed_without_writes(self, bus):
        self.assertFalse(bus.is_connected)
        self.assertEqual([event for event in bus.events if event[0] == "disconnect"], [("disconnect", False)])

    def test_discovers_ids_outside_expected_arm_and_settles_every_rate(self):
        bus = ReadOnlyBus({500_000: {42: 777, 253: 777}})
        code, report = self.invoke(bus)
        self.assertEqual(code, 0)
        self.assertEqual(report["motors"], [])
        self.assertIsNone(report["baudrate"])
        discovery = report["discovery"]
        self.assertTrue(discovery["scan_complete"])
        self.assertIsNone(discovery["motor_chain_complete"])
        self.assertFalse(discovery["calibration_verified"])
        self.assertEqual([r["id"] for r in discovery["attempts"][1]["responders"]], [42, 253])
        self.assertEqual([e[1] for e in bus.events if e[0] == "host_baud"], list(probe.DISCOVERY_BAUDRATES))
        self.assertEqual(sum(e[0] == "settle" for e in bus.events), 8)
        self.assert_closed_without_writes(bus)

    def test_no_replies_is_completed_discovery_but_not_a_working_arm(self):
        bus = ReadOnlyBus()
        code, report = self.invoke(bus)
        self.assertEqual(code, 2)
        self.assertTrue(report["discovery"]["scan_complete"])
        self.assertFalse(report["discovery"]["sts3215_response_found"])
        self.assertTrue(all(a["status"] == "no_valid_response" for a in report["discovery"]["attempts"]))
        self.assert_closed_without_writes(bus)

    def test_other_model_is_reported_without_claiming_sts3215_success(self):
        bus = ReadOnlyBus({1_000_000: {9: 2825}})
        code, report = self.invoke(bus)
        self.assertEqual(code, 2)
        self.assertEqual(report["discovery"]["attempts"][0]["responders"],
                         [{"id": 9, "model_number": 2825, "matches_sts3215": False}])
        self.assert_closed_without_writes(bus)

    def test_baud_failure_sends_no_ping_at_failed_rate_and_keeps_cleanup(self):
        bus = ReadOnlyBus({250_000: {9: 777}}, baud_failure=500_000)
        code, report = self.invoke(bus)
        self.assertEqual(code, 2)
        self.assertFalse(report["discovery"]["scan_complete"])
        self.assertTrue(report["discovery"]["sts3215_response_found"])
        self.assertEqual(report["discovery"]["attempts"][1]["status"], "error")
        self.assertNotIn(("broadcast_ping_and_model_reads", 500_000), bus.events)
        self.assert_closed_without_writes(bus)

    def test_overall_timeout_retains_partial_results_and_closes(self):
        bus = ReadOnlyBus({1_000_000: {8: 777}, 250_000: probe.ProbeTimeout("Simulated deadline")})
        code, report = self.invoke(bus)
        self.assertEqual(code, 2)
        self.assertEqual(report["errors"][0]["type"], "ProbeTimeout")
        self.assertFalse(report["discovery"]["scan_complete"])
        self.assertTrue(report["discovery"]["sts3215_response_found"])
        self.assertEqual(len(report["discovery"]["attempts"]), 3)
        self.assertEqual(report["discovery"]["attempts"][-1]["status"], "interrupted")
        self.assert_closed_without_writes(bus)

    def test_timeout_during_settling_prevents_any_ping_and_closes(self):
        bus = ReadOnlyBus()
        code, report = self.invoke(bus, sleep_error=probe.ProbeTimeout("Deadline while settling"))
        self.assertEqual(code, 2)
        self.assertFalse(any(e[0] == "broadcast_ping_and_model_reads" for e in bus.events))
        self.assertEqual(report["discovery"]["attempts"][0]["status"], "interrupted")
        self.assert_closed_without_writes(bus)

    def test_default_ping_and_read_behavior_is_preserved(self):
        bus = ReadOnlyBus(discovery_only=False)
        code, report = self.invoke(bus, flags=())
        self.assertEqual(code, 0)
        self.assertEqual(report["mode"], "ping_then_read")
        self.assertNotIn("discovery", report)
        self.assertEqual(sum(e[0] == "ping" for e in bus.events), 6)
        self.assertEqual(sum(e[0] == "read" for e in bus.events), 30)
        self.assertFalse(any(e[0] in ("host_baud", "settle") for e in bus.events))
        self.assert_closed_without_writes(bus)

    def test_direct_read_behavior_is_preserved(self):
        bus = ReadOnlyBus(discovery_only=False)
        code, report = self.invoke(bus, flags=("--direct-read",))
        self.assertEqual(code, 0)
        self.assertEqual(report["mode"], "direct_read")
        self.assertEqual(sum(e[0] == "read" for e in bus.events), 12)
        self.assertEqual(sum(e[0] == "settle" for e in bus.events), 1)
        self.assertFalse(any(e[0] in ("host_baud", "ping") for e in bus.events))
        self.assert_closed_without_writes(bus)

    def test_close_failure_is_not_reported_as_success(self):
        bus = ReadOnlyBus({1_000_000: {8: 777}}, stop_failure=True)
        code, report = self.invoke(bus)
        self.assertEqual(code, 2)
        self.assertIn("Failed to confirm", report["cleanup"])
        self.assertEqual(report["errors"][-1]["operation"], "close")

    def test_receive_window_matches_audited_sdk_constants(self):
        self.assertAlmostEqual(probe.broadcast_receive_timeout_ms(1_000_000), 787.12)
        self.assertAlmostEqual(probe.broadcast_receive_timeout_ms(19_200), 1559.5)
        self.assertAlmostEqual(sum(map(probe.broadcast_receive_timeout_ms, probe.DISCOVERY_BAUDRATES)), 7974.965)


if __name__ == "__main__":
    unittest.main()

"""Current collision-hold checks and historical fake-bus control regression tests."""

from contextlib import ExitStack, redirect_stdout
from copy import deepcopy
import hashlib
import io
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import Mock, patch


sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import so101_three_point as cli


def calibration():
    return {name: {"id": index, "drive_mode": 0, "homing_offset": index * 10,
                   "range_min": 100, "range_max": 3900}
            for index, name in enumerate(cli.JOINTS, 1)}


def pose(value=2000):
    return dict.fromkeys(cli.JOINTS, value)


class Clock:
    def __init__(self):
        self.now = 0.0

    def monotonic(self):
        return self.now

    def sleep(self, seconds):
        self.now += seconds


class MemoryJournal:
    def __init__(self):
        self.events = []

    def emit(self, kind, **fields):
        self.events.append({"kind": kind, **deepcopy(fields)})


class FakeBus:
    """Raw register fake that applies goal writes before an optional lost ACK."""

    port = "/dev/never-opened-test-follower"

    def __init__(self, cal, clock):
        self.clock = clock
        self.events = []
        self.read_delay = 0.0
        self.connected = False
        self.closed = False
        self.write_hook = None
        self.read_hook = None
        self.close_error = None
        self.rows = {}
        for name, entry in cal.items():
            self.rows[name] = {
                "Model_Number": 777, "Operating_Mode": 0, "Phase": 12,
                "Angular_Resolution": 1, "Homing_Offset": entry["homing_offset"],
                "Min_Position_Limit": entry["range_min"],
                "Max_Position_Limit": entry["range_max"],
                "Present_Position": 2000, "Status": 0, "Torque_Enable": 0,
                "Present_Voltage": 120, "Present_Temperature": 25,
                "Goal_Position": 777, "Goal_Velocity": 321, "Acceleration": 9,
            }

    @property
    def writes(self):
        return [item for item in self.events if item[0] == "write"]

    def connect(self, *, handshake):
        self.events.append(("connect", handshake))
        self.connected = True

    def read(self, register, joint, *, normalize, num_retry):
        if normalize is not False or num_retry != 0:
            raise AssertionError("Tests require the reviewed raw, no-retry path")
        self.events.append(("read", register, joint))
        self.clock.now += self.read_delay
        if self.read_hook:
            self.read_hook(register, joint)
        return self.rows[joint][register]

    def write(self, register, joint, value, *, normalize, num_retry):
        if normalize is not False or num_retry != 0:
            raise AssertionError("Tests require explicit raw writes without retries")
        self.events.append(("write", register, joint, value))
        self.rows[joint][register] = value
        if register == "Goal_Position":
            self.rows[joint]["Torque_Enable"] = 1
            self.rows[joint]["Present_Position"] = value
        if self.write_hook:
            self.write_hook(register, joint, value)

    def disconnect(self, *, disable_torque):
        self.events.append(("disconnect", disable_torque))
        self.connected = False
        self.closed = True
        if self.close_error:
            raise self.close_error


class HistoricalFollowerIOTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.directory = Path(self.temporary.name)
        self.cal = calibration()
        self.cal_path = self.directory / "calibration.json"
        self.cal_path.write_text(json.dumps(self.cal))
        self.digest = hashlib.sha256(self.cal_path.read_bytes()).hexdigest()
        self.clock = Clock()
        self.bus = FakeBus(self.cal, self.clock)
        self.stdout = io.StringIO()
        self.stack = ExitStack()
        self.addCleanup(self.stack.close)
        self.stack.enter_context(patch.object(cli, "CALIBRATION", self.cal_path))
        self.stack.enter_context(patch.object(cli.time, "monotonic", self.clock.monotonic))
        self.stack.enter_context(patch.object(cli.time, "sleep", self.clock.sleep))
        self.stack.enter_context(redirect_stdout(self.stdout))
        # Only this injected-bus regression class bypasses the production hold.
        # It checks historical control/cleanup paths, not currently enabled replay.
        # ReplayHoldTests below always exercise the real, unpatched collision gate.
        self.stack.enter_context(patch.object(cli, "require_replay_clearance", return_value=None))

    def teaching(self, points=None, **changes):
        points = points or [pose(), pose(2020), pose(2010)]
        record = {
            "schemaVersion": 1, "serial": cli.SERIAL, "calibration_id": cli.CAL_ID,
            "calibration_sha256": self.digest, "position_units": "raw_encoder_counts",
            "physical_replay_verified": False,
            "samples": [{"captured_at": f"2026-11-15T08:00:0{i}Z", "positions": p}
                        for i, p in enumerate(points)],
        }
        record.update(changes)
        return record

    def input_file(self, record=None):
        path = self.directory / "teaching.json"
        path.write_text(json.dumps(record or self.teaching()))
        return path

    def run_main(self, mode, *, record=None, input_effect=None, open_effect=None, extra_args=()):
        journal = self.directory / f"{mode}-{len(list(self.directory.glob('*.jsonl')))}.jsonl"
        args = [mode, "--journal", str(journal), "--operator-ready"]
        if mode == "teach":
            args.extend(["--output", str(self.directory / "captured.json")])
        else:
            args.extend(["--input", str(self.input_file(record))])
        args.extend(extra_args)

        def open_fake(follower):
            follower.bus.connect(handshake=False)
            if open_effect:
                open_effect(follower)

        with ExitStack() as stack:
            stack.enter_context(patch.object(cli, "resolve_port", return_value=Path(self.bus.port)))
            stack.enter_context(patch.object(cli, "make_bus", return_value=self.bus))
            stack.enter_context(patch.object(cli.Follower, "open", open_fake))
            stack.enter_context(patch.object(cli.signal, "signal", return_value=cli.signal.SIG_DFL))
            self.timer = stack.enter_context(patch.object(cli.signal, "setitimer"))
            stack.enter_context(patch("builtins.input", side_effect=input_effect or ["", "", "", "done"]))
            status = cli.main(args)
        events = [json.loads(line) for line in journal.read_text().splitlines()]
        return status, events

    def follower(self):
        return cli.Follower(self.bus, self.cal, MemoryJournal())

    def assert_no_goals(self):
        self.assertFalse(any(row[1] == "Goal_Position" for row in self.bus.writes))

    def assert_closed_without_implicit_torque(self):
        self.assertTrue(self.bus.closed)
        self.assertEqual(self.bus.events[-1], ("disconnect", False))

    def test_teach_saves_three_actual_poses_without_any_goal_or_enable(self):
        points = [pose(1800), pose(1840), pose(1810)]
        count = 0

        def operator(_prompt):
            nonlocal count
            if count == 3:
                return "done"
            for joint in cli.JOINTS:
                self.bus.rows[joint]["Present_Position"] = points[count][joint]
            count += 1
            return ""

        status, events = self.run_main("teach", input_effect=operator)
        data = json.loads((self.directory / "captured.json").read_text())
        self.assertEqual(status, 0)
        self.assertEqual([row["positions"] for row in data["samples"]], points)
        self.assertEqual(data["calibration_sha256"], self.digest)
        self.assertEqual(data["serial"], cli.SERIAL)
        self.assertFalse(data["physical_replay_verified"])
        self.assertEqual(len([row for row in events if row["kind"] == "point_captured"]), 3)
        self.assertTrue(all(row[1] == "Torque_Enable" and row[3] == 0 for row in self.bus.writes))
        self.assert_no_goals()
        self.assert_closed_without_implicit_torque()

    def test_teach_interrupt_retains_no_complete_capture_and_cleans_every_joint(self):
        status, events = self.run_main("teach", input_effect=["", KeyboardInterrupt()])
        self.assertEqual(status, 1)
        self.assertFalse((self.directory / "captured.json").exists())
        self.assertEqual(len([row for row in events if row["kind"] == "point_captured"]), 1)
        self.assert_no_goals()
        self.assertEqual({row[2] for row in self.bus.writes}, set(cli.JOINTS))
        self.assert_closed_without_implicit_torque()

    def test_calibration_change_between_teaching_points_rejects_next_point_and_save(self):
        prompts = 0

        def operator(_prompt):
            nonlocal prompts
            prompts += 1
            if prompts == 2:
                self.cal_path.write_text(json.dumps(self.cal) + "\n")
            return ""

        status, events = self.run_main("teach", input_effect=operator)
        self.assertEqual(status, 1)
        self.assertFalse((self.directory / "captured.json").exists())
        self.assertEqual(len([row for row in events if row["kind"] == "point_captured"]), 1)
        self.assert_no_goals()
        self.assert_closed_without_implicit_torque()

    def test_calibration_change_after_last_capture_rejects_complete_save(self):
        original_emit = cli.Journal.emit

        def emit(journal, kind, **fields):
            original_emit(journal, kind, **fields)
            if kind == "point_captured" and fields["number"] == 3:
                self.cal_path.write_text(json.dumps(self.cal) + "\n")

        with patch.object(cli.Journal, "emit", emit):
            status, events = self.run_main("teach")
        self.assertEqual(status, 1)
        self.assertFalse((self.directory / "captured.json").exists())
        self.assertEqual(len([row for row in events if row["kind"] == "point_captured"]), 3)
        self.assert_no_goals()
        self.assert_closed_without_implicit_torque()

    def test_plan_never_resolves_or_constructs_a_bus(self):
        path = self.input_file()
        with patch.object(cli, "resolve_port") as resolve, patch.object(cli, "make_bus") as construct:
            self.assertEqual(cli.main(["plan", "--input", str(path)]), 0)
        resolve.assert_not_called()
        construct.assert_not_called()
        self.assertEqual(self.bus.events, [])

    def test_24_second_segments_preserve_points_and_existing_speed_and_step_limits(self):
        points = [pose(), {**pose(), "shoulder_pan": 2932}, pose()]
        path = self.input_file(self.teaching(points))
        output = self.directory / "plan.json"
        with patch.object(cli, "make_bus") as construct:
            self.assertEqual(cli.main(["plan", "--input", str(path), "--output", str(output),
                                       "--segment-s", "24"]), 0)
        construct.assert_not_called()
        plan = json.loads(output.read_text())
        self.assertEqual(plan["duration_s"], 48)
        self.assertEqual(len(plan["frames"]), 481)
        self.assertEqual(plan["inputposes"], points)
        self.assertEqual(plan["frames"][240]["positions"], points[1])
        self.assertEqual(plan["limits"]["max_speed_counts_s"], 80)
        self.assertEqual(plan["limits"]["max_step_counts"], 8)
        self.assertAlmostEqual(plan["max_speed_counts_s"]["shoulder_pan"], 72.8125)
        self.assertLessEqual(max(plan["observed_max_step_counts"].values()), 8)

    def test_excessive_speed_is_rejected_without_clamping_even_with_longer_segments(self):
        for seconds, delta in [(15, 932), (24, 1200)]:
            with self.subTest(seconds=seconds):
                path = self.input_file(self.teaching([pose(), {**pose(), "shoulder_pan": 2000 + delta}, pose()]))
                output = self.directory / f"rejected-{seconds}.json"
                with self.assertRaisesRegex(ValueError, "speed bound"):
                    cli.main(["plan", "--input", str(path), "--output", str(output),
                              "--segment-s", str(seconds)])
                self.assertFalse(output.exists())
        self.assertEqual(self.bus.events, [])

    def test_invalid_segment_durations_reject_before_calibration_or_bus(self):
        for value in ("nan", "inf", "-inf", "-1", "0", "14.9", "60.1"):
            with self.subTest(value=value), patch.object(cli, "read_json") as read:
                with self.assertRaisesRegex(ValueError, "Segment duration"):
                    cli.main(["plan", f"--segment-s={value}"])
                read.assert_not_called()
        self.assertEqual(self.bus.events, [])

    def test_alignment_near_first_point_never_writes_any_register(self):
        status, events = self.run_main("align")
        self.assertEqual(status, 0)
        self.assertEqual(self.bus.writes, [])
        self.assertEqual([e for e in events if e["kind"] == "alignment"][0]["delta"], pose(0))
        self.assertEqual(events[-1]["outcome"], "alignment_verified_no_writes")
        self.assert_closed_without_implicit_torque()

    def test_alignment_torque_on_rejects_without_releasing_or_writing(self):
        self.bus.rows[cli.JOINTS[0]]["Torque_Enable"] = 1
        status, _ = self.run_main("align")
        self.assertEqual(status, 1)
        self.assertEqual(self.bus.writes, [])
        self.assertEqual(self.bus.rows[cli.JOINTS[0]]["Torque_Enable"], 1)
        self.assert_closed_without_implicit_torque()

    def test_distant_alignment_waits_for_operator_and_only_observes_manual_change(self):
        def operator(_prompt):
            self.assertEqual(self.bus.writes, [])
            for row in self.bus.rows.values():
                row["Present_Position"] = 2200
            return ""

        status, events = self.run_main("align", record=self.teaching([pose(2200)] * 3), input_effect=operator)
        self.assertEqual(status, 0)
        observed = [e["delta"] for e in events if e["kind"] == "alignment"]
        self.assertEqual(observed, [pose(-200), pose(0)])
        self.assertEqual(self.bus.writes, [])
        self.assert_closed_without_implicit_torque()

    def test_operator_can_stop_distant_alignment_without_motor_writes(self):
        status, events = self.run_main("align", record=self.teaching([pose(2200)] * 3), input_effect=["stop"])
        self.assertEqual(status, 1)
        self.assertEqual(events[-1]["outcome"], "aborted")
        self.assertEqual(self.bus.writes, [])
        self.assert_closed_without_implicit_torque()

    def test_longer_replay_reports_actual_plan_duration_and_bounded_deadline(self):
        status, events = self.run_main("replay", extra_args=["--segment-s", "24"])
        self.assertEqual(status, 0)
        completion = next(e for e in events if e["kind"] == "commanded_path_completed")
        self.assertEqual(completion["nominal_path_seconds"], 49)
        self.assertAlmostEqual(completion["actual_path_seconds"], 49)
        self.assertEqual(self.timer.call_args_list[0].args, (cli.signal.ITIMER_REAL, 88.5))
        self.assertEqual(self.timer.call_args_list[-1].args, (cli.signal.ITIMER_REAL, 0))
        self.assert_closed_without_implicit_torque()

    def test_three_round_repeat_retraces_only_adjacent_segments_from_point_three(self):
        points = [pose(1800), {**pose(1800), "shoulder_pan": 2732}, pose(1810)]
        original = deepcopy(points)
        plan = cli.build_plan(points, self.cal, segment_s=24, repeat=3, start_point=3)
        route = [3, 2, 1, 2, 3, 2, 1, 2, 3, 2, 1, 2, 3]
        self.assertEqual(plan["route_point_numbers"], route)
        self.assertEqual(plan["duration_s"], 288)
        self.assertEqual(len(plan["frames"]), 2881)
        self.assertEqual(plan["frames"][0]["positions"], points[2])
        self.assertEqual(plan["frames"][-1]["positions"], points[2])
        self.assertEqual(plan["end_pose"], points[2])
        self.assertEqual(points, original)
        self.assertEqual(plan["limits"]["max_speed_counts_s"], 80)
        self.assertEqual(plan["limits"]["max_step_counts"], 8)
        for number, point in enumerate(route):
            self.assertEqual(plan["frames"][number * 240]["positions"], points[point - 1])
        for first, second in zip(plan["frames"], plan["frames"][1:]):
            self.assertAlmostEqual(second["offset_s"] - first["offset_s"], 0.1)
            self.assertTrue(all(abs(second["positions"][j] - first["positions"][j]) <= 8
                                for j in cli.JOINTS))

    def test_repeat_round_counts_and_both_start_points_have_exact_endpoints(self):
        points = [pose(), pose(2020), pose(2010)]
        for start in (1, 3):
            for repeat in (1, 2, 3):
                with self.subTest(start=start, repeat=repeat):
                    plan = cli.build_plan(points, self.cal, repeat=repeat, start_point=start)
                    self.assertEqual(plan["duration_s"], repeat * 60)
                    self.assertEqual(len(plan["frames"]), repeat * 600 + 1)
                    self.assertEqual(plan["frames"][0]["positions"], points[start - 1])
                    self.assertEqual(plan["frames"][-1]["positions"], points[start - 1])

    def test_invalid_repeat_counts_and_start_points_are_rejected(self):
        points = [pose(), pose(2020), pose(2010)]
        for repeat in (True, False, 0, -1, 4, 1.5, "3"):
            with self.subTest(repeat=repeat), self.assertRaises(ValueError):
                cli.build_plan(points, self.cal, repeat=repeat)
        for start in (True, False, 0, 2, 4, 1.0, "3"):
            with self.subTest(start=start), self.assertRaises(ValueError):
                cli.build_plan(points, self.cal, start_point=start)
        self.assertEqual(self.bus.events, [])

    def test_nonrepeated_reverse_route_remains_one_way_and_preserves_input(self):
        points = [pose(), pose(2020), pose(2010)]
        original = deepcopy(points)
        plan = cli.build_plan(points, self.cal, start_point=3)
        self.assertEqual(plan["route_point_numbers"], [3, 2, 1])
        self.assertEqual(plan["duration_s"], 30)
        self.assertEqual(len(plan["frames"]), 301)
        self.assertEqual(plan["frames"][-1]["positions"], points[0])
        self.assertEqual(points, original)

    def test_complete_fake_three_round_replay_finishes_point_three_with_bounded_deadline(self):
        for row in self.bus.rows.values():
            row["Present_Position"] = 2010
        status, events = self.run_main("replay", extra_args=["--segment-s", "24", "--repeat", "3",
                                                           "--start-point", "3"])
        self.assertEqual(status, 0)
        completion = next(e for e in events if e["kind"] == "commanded_path_completed")
        self.assertEqual(completion["final_position"], pose(2010))
        self.assertEqual(completion["nominal_path_seconds"], 289)
        self.assertAlmostEqual(completion["actual_path_seconds"], 289)
        self.assertEqual(completion["operator_observation"], "pending")
        self.assertEqual(self.timer.call_args_list[0].args, (cli.signal.ITIMER_REAL, 448.5))
        self.assertTrue(all(row["Torque_Enable"] == 0 for row in self.bus.rows.values()))
        self.assert_closed_without_implicit_torque()

    def test_missing_operator_confirmation_rejects_before_bus_or_journal(self):
        path = self.input_file()
        journal = self.directory / "never-created.jsonl"
        with patch.object(cli, "resolve_port") as resolve, patch.object(cli, "make_bus") as construct:
            with self.assertRaises(ValueError):
                cli.main(["replay", "--input", str(path), "--journal", str(journal)])
        resolve.assert_not_called()
        construct.assert_not_called()
        self.assertFalse(journal.exists())

    def test_identity_hash_and_units_mismatch_reject_before_bus(self):
        for changes in [{"serial": "other"}, {"calibration_id": "other"},
                        {"calibration_sha256": "0" * 64}, {"position_units": "degrees"}]:
            with self.subTest(changes=changes):
                path = self.input_file(self.teaching(**changes))
                with patch.object(cli, "resolve_port") as resolve, patch.object(cli, "make_bus") as construct:
                    with self.assertRaises(ValueError):
                        cli.main(["replay", "--input", str(path), "--operator-ready"])
                resolve.assert_not_called()
                construct.assert_not_called()

    def test_boolean_schema_version_is_not_version_one(self):
        path = self.input_file(self.teaching(schemaVersion=True))
        with self.assertRaises(ValueError):
            cli.load_teaching(path, self.cal, self.digest)

    def test_duplicate_json_keys_are_rejected(self):
        path = self.directory / "duplicate.json"
        path.write_text('{"serial":"untrusted","serial":"5AE6075066"}')
        with self.assertRaises(ValueError):
            cli.read_json(path)

    def test_nonfinite_json_is_rejected(self):
        for token in ("NaN", "Infinity", "-Infinity"):
            with self.subTest(token=token):
                path = self.directory / "nonfinite.json"
                path.write_text('{"value":' + token + '}')
                with self.assertRaises(ValueError):
                    cli.read_json(path)

    def test_distant_start_rejects_before_any_register_write(self):
        status, events = self.run_main("replay", record=self.teaching([pose(2200)] * 3))
        self.assertEqual(status, 1)
        self.assertEqual(self.bus.writes, [])
        self.assertFalse(any(row["kind"] == "commanded_path_completed" for row in events))
        self.assert_closed_without_implicit_torque()

    def test_replay_does_not_release_an_already_powered_arm(self):
        self.bus.rows[cli.JOINTS[0]]["Torque_Enable"] = 1
        status, _ = self.run_main("replay")
        self.assertEqual(status, 1)
        self.assertEqual(self.bus.writes, [])
        self.assertEqual(self.bus.rows[cli.JOINTS[0]]["Torque_Enable"], 1)
        self.assert_closed_without_implicit_torque()

    def test_configuration_mismatch_is_never_repaired(self):
        for register in ("Homing_Offset", "Min_Position_Limit", "Operating_Mode", "Phase", "Model_Number"):
            with self.subTest(register=register):
                self.bus.rows[cli.JOINTS[0]][register] += 1
                status, _ = self.run_main("replay")
                self.assertEqual(status, 1)
                self.assertEqual(self.bus.writes, [])
                self.assert_closed_without_implicit_torque()
                self.bus.rows[cli.JOINTS[0]][register] -= 1

    def test_status_alarm_rejects_even_when_read_itself_succeeds(self):
        self.bus.rows["gripper"]["Status"] = 1
        status, _ = self.run_main("replay")
        self.assertEqual(status, 1)
        self.assertEqual(self.bus.writes, [])
        self.assert_closed_without_implicit_torque()

    def test_stale_telemetry_rejects_before_writes(self):
        self.bus.read_delay = 0.02
        status, _ = self.run_main("replay")
        self.assertEqual(status, 1)
        self.assertEqual(self.bus.writes, [])
        self.assertIn("Telemetry is stale", self.stdout.getvalue())
        self.assert_closed_without_implicit_torque()

    def test_open_failure_after_acquisition_still_closes_without_writes(self):
        def fail(_follower):
            raise OSError("Injected exclusive-descriptor failure")

        status, _ = self.run_main("replay", open_effect=fail)
        self.assertEqual(status, 1)
        self.assertEqual(self.bus.writes, [])
        self.assert_closed_without_implicit_torque()

    def test_changed_calibration_before_replay_is_rejected_without_writes(self):
        plan = cli.plan_waypoints([pose()] * 3, self.cal)
        self.cal_path.write_text(json.dumps({**self.cal, "unexpected": {}}))
        with self.assertRaisesRegex(ValueError, "Calibration changed"):
            cli.replay(self.follower(), plan, self.cal, self.digest)
        self.assertEqual(self.bus.events, [])

    def test_partial_ram_setup_lost_ack_cleans_all_and_restores_only_saved_ram(self):
        lost = False

        def fault(register, _joint, _value):
            nonlocal lost
            if register == "Goal_Velocity" and not lost:
                lost = True
                raise OSError("Applied RAM write, lost acknowledgment")

        self.bus.write_hook = fault
        status, _ = self.run_main("replay")
        self.assertEqual(status, 1)
        self.assert_no_goals()
        off = [row for row in self.bus.writes if row[1] == "Torque_Enable"]
        self.assertEqual({row[2] for row in off}, set(cli.JOINTS))
        self.assertTrue(all(row[3] == 0 for row in off))
        self.assertEqual(self.bus.rows[cli.JOINTS[0]]["Goal_Velocity"], 321)
        self.assertEqual(self.bus.rows[cli.JOINTS[0]]["Acceleration"], 9)
        self.assert_closed_without_implicit_torque()

    def test_lost_ack_after_goal_energizes_then_all_joint_cleanup_runs(self):
        lost = False

        def fault(register, joint, _value):
            nonlocal lost
            if register == "Goal_Position" and not lost:
                lost = True
                self.assertEqual(self.bus.rows[joint]["Torque_Enable"], 1)
                raise OSError("Goal applied, acknowledgment lost")

        self.bus.write_hook = fault
        status, events = self.run_main("replay")
        self.assertEqual(status, 1)
        goals = [row for row in self.bus.writes if row[1] == "Goal_Position"]
        self.assertEqual(len(goals), 1)
        self.assertNotEqual(goals[0][3], 777)
        self.assertTrue(all(self.bus.rows[j]["Torque_Enable"] == 0 for j in cli.JOINTS))
        self.assertFalse(any(row[1] == "Torque_Enable" and row[3] != 0 for row in self.bus.writes))
        self.assertTrue(next(row for row in events if row["kind"] == "cleanup")["completed"])
        self.assert_closed_without_implicit_torque()

    def test_cleanup_attempts_all_off_writes_before_reads_and_never_restores_a_goal(self):
        follower = self.follower()
        follower.writes_started = True
        follower.original_ram = {name: {"Goal_Velocity": 321, "Acceleration": 9} for name in cli.JOINTS}
        for row in self.bus.rows.values():
            row["Torque_Enable"] = 1
        self.assertTrue(follower.cleanup())
        self.assertEqual(self.bus.events[:6], [("write", "Torque_Enable", j, 0) for j in cli.JOINTS])
        self.assertEqual(self.bus.events[6:12], [("read", "Torque_Enable", j) for j in cli.JOINTS])
        self.assert_no_goals()
        self.assertFalse(any(row[1] == "Torque_Enable" and row[3] != 0 for row in self.bus.writes))
        self.assert_closed_without_implicit_torque()

    def test_cleanup_read_failure_continues_other_joints_skips_ram_restore_and_closes(self):
        follower = self.follower()
        follower.writes_started = True
        follower.original_ram = {j: {"Goal_Velocity": 321, "Acceleration": 9} for j in cli.JOINTS}

        def fail(register, joint):
            if register == "Torque_Enable" and joint == cli.JOINTS[0]:
                raise OSError("Injected failed torque verification")

        self.bus.read_hook = fail
        self.assertFalse(follower.cleanup())
        self.assertEqual({row[2] for row in self.bus.writes}, set(cli.JOINTS))
        self.assertTrue(all(row[1] == "Torque_Enable" for row in self.bus.writes))
        self.assertEqual(len([row for row in self.bus.events if row[0] == "read"]), 6)
        self.assert_closed_without_implicit_torque()

    def test_cleanup_detects_torque_changed_during_ram_restore_and_releases_again(self):
        follower = self.follower()
        follower.writes_started = True
        joint = cli.JOINTS[0]
        follower.original_ram = {joint: {"Goal_Velocity": 321, "Acceleration": 9}}

        def change(register, target, _value):
            if register == "Goal_Velocity":
                self.bus.rows[target]["Torque_Enable"] = 1

        self.bus.write_hook = change
        self.assertFalse(follower.cleanup())
        cleanup = follower.journal.events[-1]
        self.assertTrue(cleanup["torque_off"][joint])
        self.assertIn("torque changed during RAM restoration", cleanup["errors"][0])
        self.assertEqual(len([row for row in self.bus.writes
                              if row[1:3] == ("Torque_Enable", joint)]), 2)
        self.assert_no_goals()
        self.assert_closed_without_implicit_torque()

    def test_cleanup_off_write_failure_does_not_skip_other_motors(self):
        follower = self.follower()
        follower.writes_started = True

        def fail(register, joint, _value):
            if register == "Torque_Enable" and joint == cli.JOINTS[0]:
                raise OSError("Injected cleanup acknowledgment failure")

        self.bus.write_hook = fail
        self.assertFalse(follower.cleanup())
        self.assertEqual({row[2] for row in self.bus.writes}, set(cli.JOINTS))
        self.assert_closed_without_implicit_torque()

    def test_close_failure_is_not_success(self):
        follower = self.follower()
        self.bus.close_error = OSError("Injected close failure")
        self.assertFalse(follower.cleanup())
        self.assertFalse(follower.journal.events[-1]["completed"])
        self.assertIn("Port close", follower.journal.events[-1]["errors"][0])

    def test_allowlist_rejects_eeprom_positive_torque_and_unbound_stale_goal(self):
        follower = self.follower()
        for register, value in [("Homing_Offset", 20), ("Min_Position_Limit", 100),
                                ("Operating_Mode", 0), ("Torque_Enable", 1),
                                ("Goal_Position", 777)]:
            with self.subTest(register=register), self.assertRaises(ValueError):
                follower.write(register, cli.JOINTS[0], value)
        self.assertEqual(self.bus.writes, [])
        self.assertFalse(follower.writes_started)

    def test_step_or_calibrated_margin_violation_rejects_before_writes(self):
        follower = self.follower()
        follower.goals = pose()
        for target in (pose(2009), pose(100)):
            with self.subTest(target=target), self.assertRaises(ValueError):
                follower.send_pose(target)
        self.assertEqual(self.bus.events, [])

    def test_calibration_change_after_hold_prevents_route_commands_and_cleans(self):
        changed = False

        def change(register, _joint, _value):
            nonlocal changed
            if register == "Goal_Position" and not changed:
                changed = True
                self.cal_path.write_text(json.dumps(self.cal) + "\n")

        self.bus.write_hook = change
        status, events = self.run_main("replay")
        self.assertEqual(status, 1)
        self.assertFalse(any(row["kind"] == "commanded_path_completed" for row in events))
        self.assertLessEqual(len([row for row in self.bus.writes if row[1] == "Goal_Position"]), 6)
        self.assertTrue(all(self.bus.rows[j]["Torque_Enable"] == 0 for j in cli.JOINTS))
        self.assert_closed_without_implicit_torque()

    def test_completed_fake_route_restores_ram_only_after_off_and_never_old_goals(self):
        status, events = self.run_main("replay")
        self.assertEqual(status, 0)
        completion = [row for row in events if row["kind"] == "commanded_path_completed"]
        self.assertEqual(len(completion), 1)
        self.assertEqual(completion[0]["operator_observation"], "pending")
        self.assertEqual(completion[0]["final_position"], pose(2010))
        allowed = {"Torque_Enable", "Goal_Position", "Goal_Velocity", "Acceleration"}
        self.assertTrue(all(row[1] in allowed for row in self.bus.writes))
        self.assertTrue(all(row[3] != 777 for row in self.bus.writes if row[1] == "Goal_Position"))
        self.assertTrue(all(row[3] == 0 for row in self.bus.writes if row[1] == "Torque_Enable"))
        for row in self.bus.rows.values():
            self.assertEqual(row["Torque_Enable"], 0)
            self.assertEqual(row["Goal_Velocity"], 321)
            self.assertEqual(row["Acceleration"], 9)
        self.assert_closed_without_implicit_torque()

    def test_approach_starts_from_each_actual_hold_goal_after_small_passive_drift(self):
        drifted = False

        def drift(register, _joint, _value):
            nonlocal drifted
            if register == "Goal_Position" and not drifted:
                drifted = True
                for joint in cli.JOINTS[1:]:
                    self.bus.rows[joint]["Present_Position"] = 2007

        self.bus.write_hook = drift
        status, _ = self.run_main("replay")
        self.assertEqual(status, 0)
        actual_hold = {joint: 2000 if index == 0 else 2007
                       for index, joint in enumerate(cli.JOINTS)}
        expected_first = cli.interpolate_pose(actual_hold, pose(), 0.1)
        for joint in cli.JOINTS:
            goals = [row[3] for row in self.bus.writes
                     if row[1:3] == ("Goal_Position", joint)]
            self.assertEqual(goals[0], actual_hold[joint])
            self.assertEqual(goals[1], expected_first[joint])
        self.assert_closed_without_implicit_torque()


class ReplayHoldTests(unittest.TestCase):
    """The real collision gate must reject before filesystem or motor I/O."""

    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.directory = Path(self.temporary.name)
        self.stdout = io.StringIO()

    def assert_main_is_blocked_without_io(self, args):
        # Missing paths deliberately ensure the hold cannot depend on valid data.
        missing_calibration = self.directory / "missing-calibration.json"
        spies = {}
        with ExitStack() as stack:
            stack.enter_context(redirect_stdout(self.stdout))
            stack.enter_context(patch.object(cli, "CALIBRATION", missing_calibration))
            for name in ("read_json", "load_teaching", "build_plan", "Journal", "resolve_port",
                         "make_bus", "Follower"):
                spies[name] = stack.enter_context(patch.object(
                    cli, name, side_effect=AssertionError(f"Hold unexpectedly reached {name}")))
            timer = stack.enter_context(patch.object(cli.signal, "setitimer"))
            self.assertEqual(cli.main(["replay", *args]), 1)
        for spy in spies.values():
            spy.assert_not_called()
        timer.assert_not_called()
        self.assertEqual(list(self.directory.iterdir()), [])
        self.assertIn("Replay disabled", self.stdout.getvalue())
        self.assertIn("table collision", self.stdout.getvalue())

    def test_missing_input_and_calibration_do_not_bypass_or_precede_hold(self):
        self.assert_main_is_blocked_without_io([])

    def test_operator_ready_and_repeat_flags_cannot_bypass_hold(self):
        self.assert_main_is_blocked_without_io([
            "--input", str(self.directory / "missing-points.json"),
            "--journal", str(self.directory / "missing-parent" / "never-created.jsonl"),
            "--segment-s=24", "--repeat=3", "--start-point=3", "--operator-ready",
        ])

    def test_hold_precedes_duration_validation_and_journal_creation(self):
        self.assert_main_is_blocked_without_io([
            "--segment-s=nan", "--operator-ready", "--journal", str(self.directory / "never-created.jsonl"),
        ])

    def test_direct_replay_is_blocked_before_calibration_or_follower_access(self):
        follower = Mock()
        calibration_path = Mock()
        calibration_path.read_bytes.side_effect = AssertionError("Calibration read before collision hold")
        with patch.object(cli, "CALIBRATION", calibration_path):
            with self.assertRaisesRegex(ValueError, "Replay disabled.*table collision"):
                cli.replay(follower, {}, None, "unused")
        calibration_path.read_bytes.assert_not_called()
        self.assertEqual(follower.mock_calls, [])

    def test_clearance_gate_unconditionally_requires_separate_review(self):
        with self.assertRaisesRegex(ValueError, "Physical inspection and a reviewed path"):
            cli.require_replay_clearance()


if __name__ == "__main__":
    unittest.main()

"""Offline planner checks; no hardware imports, device opens or execution."""
import copy
import json
import math
import unittest

from scripts.so101_three_point_core import (
    CAL_ID, JOINTS, SERIAL, interpolate_pose, plan_waypoints, validate_calibration, validate_pose,
)


def calibration(low=0, high=4095):
    return {name: {"id": index, "drive_mode": 0, "homing_offset": 0,
                   "range_min": low, "range_max": high}
            for index, name in enumerate(JOINTS, 1)}


def pose(value=2000):
    return dict.fromkeys(JOINTS, value)


class CalibrationTests(unittest.TestCase):
    def test_valid_calibration_is_copied(self):
        source = calibration()
        result = validate_calibration(source)
        self.assertEqual(result, source)
        result[JOINTS[0]]["range_min"] = 100
        self.assertEqual(source[JOINTS[0]]["range_min"], 0)

    def test_joint_set_must_be_exact(self):
        for value in [None, [], {}, {**calibration(), "extra": {}}]:
            with self.subTest(value=value), self.assertRaises(ValueError):
                validate_calibration(value)

    def test_missing_fields_wrong_ids_and_boolean_values_rejected(self):
        changes = [("id", 2), ("id", True), ("drive_mode", 2), ("homing_offset", 1.5),
                   ("range_min", False), ("range_max", float("nan"))]
        for field, value in changes:
            data = calibration()
            data[JOINTS[0]][field] = value
            with self.subTest(field=field, value=value), self.assertRaises(ValueError):
                validate_calibration(data)
        data = calibration()
        del data[JOINTS[0]]["id"]
        with self.assertRaises(ValueError):
            validate_calibration(data)

    def test_calibration_raw_ranges_rejected(self):
        for low, high in [(-1, 4000), (0, 4096), (100, 100), (200, 100)]:
            with self.subTest(low=low, high=high), self.assertRaises(ValueError):
                validate_calibration(calibration(low, high))


class PoseTests(unittest.TestCase):
    def test_margin_boundaries_are_inclusive(self):
        cal = calibration(100, 3000)
        self.assertEqual(validate_pose(pose(132), cal), pose(132))
        self.assertEqual(validate_pose(pose(2968), cal), pose(2968))
        for value in (131, 2969):
            with self.subTest(value=value), self.assertRaises(ValueError):
                validate_pose(pose(value), cal)

    def test_invalid_raw_values_and_joint_sets_rejected(self):
        for value in [True, False, 2000.0, "2000", None, math.nan, math.inf, -1, 4096]:
            data = pose()
            data["gripper"] = value
            with self.subTest(value=value), self.assertRaises(ValueError):
                validate_pose(data, calibration())
        data = pose()
        del data["wrist_roll"]
        with self.assertRaises(ValueError):
            validate_pose(data, calibration())
        with self.assertRaises(ValueError):
            validate_pose({**pose(), "extra": 1}, calibration())

    def test_invalid_or_impossible_margin_rejected(self):
        for margin in [True, -1, 0.5, math.inf]:
            with self.subTest(margin=margin), self.assertRaises(ValueError):
                validate_pose(pose(), calibration(), margin)
        with self.assertRaises(ValueError):
            validate_pose(pose(100), calibration(90, 110))


class InterpolationTests(unittest.TestCase):
    def test_exact_endpoints_copies_and_stationary_pose(self):
        first, last = pose(1000), pose(2001)
        self.assertEqual(interpolate_pose(first, last, 0), first)
        self.assertEqual(interpolate_pose(first, last, 1), last)
        self.assertIsNot(interpolate_pose(first, last, 0), first)
        self.assertEqual(interpolate_pose(first, first, 0.37), first)

    def test_monotonic_no_overshoot_in_both_directions(self):
        first, last = pose(1000), pose(2001)
        first["gripper"], last["gripper"] = 3000, 1999
        samples = [interpolate_pose(first, last, step / 1000) for step in range(1001)]
        for name in JOINTS:
            values = [sample[name] for sample in samples]
            self.assertTrue(all(min(first[name], last[name]) <= value <= max(first[name], last[name])
                                for value in values))
            self.assertEqual(values, sorted(values, reverse=last[name] < first[name]))
            self.assertTrue(all(type(value) is int for value in values))

    def test_invalid_progress_rejected(self):
        for value in [True, None, "0.5", math.nan, math.inf, -math.inf, -0.001, 1.001, 10**400]:
            with self.subTest(value=value), self.assertRaises(ValueError):
                interpolate_pose(pose(), pose(), value)

    def test_malformed_endpoint_rejected(self):
        with self.assertRaises(ValueError):
            interpolate_pose(pose(), {"shoulder_pan": 2000}, 0.5)


class PlanningTests(unittest.TestCase):
    def test_default_plan_has_exact_endpoints_and_no_extra_return(self):
        points = [pose(1800), pose(2100), pose(1950)]
        original = copy.deepcopy(points)
        plan = plan_waypoints(points, calibration())
        self.assertEqual(len(plan["frames"]), 301)
        self.assertEqual(plan["duration_s"], 30.0)
        for index, point in [(0, points[0]), (150, points[1]), (300, points[2])]:
            self.assertEqual(plan["frames"][index]["positions"], point)
            self.assertEqual(plan["frames"][index]["offset_s"], index / 10)
        self.assertFalse(plan["initial_approach_included"])
        self.assertFalse(plan["return_to_start_included"])
        self.assertFalse(plan["physical_verified"])
        self.assertFalse(plan["collision_checked"])
        self.assertEqual(plan["serial"], SERIAL)
        self.assertEqual(plan["calibrationId"], CAL_ID)
        self.assertEqual(plan["class"], "software_planned")
        self.assertEqual(json.loads(json.dumps(plan, allow_nan=False)), plan)
        self.assertEqual(points, original)
        plan["frames"][0]["positions"][JOINTS[0]] = 999
        self.assertEqual(points, original)
        self.assertEqual(plan["inputposes"], original)

    def test_speed_bound_and_actual_step_bounds(self):
        first, middle, last = pose(), pose(), pose()
        middle["shoulder_pan"] += 640
        plan = plan_waypoints([first, middle, last], calibration())
        self.assertEqual(plan["max_speed_counts_s"]["shoulder_pan"], 80.0)
        for before, after in zip(plan["frames"], plan["frames"][1:]):
            self.assertGreater(after["offset_s"], before["offset_s"])
            self.assertTrue(all(abs(after["positions"][name] - before["positions"][name]) <= 8
                                for name in JOINTS))
        middle["shoulder_pan"] += 1
        with self.assertRaises(ValueError):
            plan_waypoints([first, middle, last], calibration())

    def test_wrist_long_path_and_wrap_shortcut_rejected(self):
        first, middle, last = pose(), pose(), pose()
        middle["wrist_roll"] += 512
        plan_waypoints([first, middle, last], calibration())
        middle["wrist_roll"] += 1
        with self.assertRaises(ValueError):
            plan_waypoints([first, middle, last], calibration())
        first["wrist_roll"], middle["wrist_roll"] = 64, 4000
        with self.assertRaises(ValueError):
            plan_waypoints([first, middle, last], calibration(), segment_s=100)

    def test_rounded_commands_must_satisfy_step_even_when_speed_passes(self):
        first, middle, last = pose(), pose(2200), pose()
        with self.assertRaises(ValueError):
            plan_waypoints([first, middle, last], calibration(), hz=1)
        with self.assertRaises(ValueError):
            plan_waypoints([first, middle, last], calibration(), max_step=1)

    def test_invalid_parameters_and_excessive_allocation_rejected(self):
        points = [pose(), pose(), pose()]
        for key in ["segment_s", "hz", "max_speed"]:
            for value in [0, -1, True, math.nan, math.inf, "15", None, 10**400]:
                with self.subTest(key=key, value=value), self.assertRaises(ValueError):
                    plan_waypoints(points, calibration(), **{key: value})
        for value in [0, -1, True, 1.5, math.inf]:
            with self.subTest(max_step=value), self.assertRaises(ValueError):
                plan_waypoints(points, calibration(), max_step=value)
        for kwargs in [{"segment_s": 0.01}, {"segment_s": 1.01, "hz": 10},
                       {"segment_s": 1e100}, {"segment_s": 1e200, "hz": 1e200}]:
            with self.subTest(kwargs=kwargs), self.assertRaises(ValueError):
                plan_waypoints(points, calibration(), **kwargs)

    def test_requires_three_complete_calibrated_poses(self):
        for points in [None, {}, [], [pose()], [pose()] * 2, [pose()] * 4]:
            with self.subTest(points=points), self.assertRaises(ValueError):
                plan_waypoints(points, calibration())
        with self.assertRaises(ValueError):
            plan_waypoints([pose(), pose(0), pose()], calibration())

    def test_total_duration_overflow_rejected_even_with_small_frame_count(self):
        with self.assertRaises(ValueError):
            plan_waypoints([pose()] * 3, calibration(), segment_s=1e308, hz=1e-308)


if __name__ == "__main__":
    unittest.main()

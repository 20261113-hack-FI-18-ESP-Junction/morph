"""Pure three-pose joint-space planning; no hardware access or collision checking.

Raw encoder interpolation does not establish a safe Cartesian path, cable clearance,
or physical acceptance. Device identity, calibration hashes, approach and execution
authorization belong to the separate hardware adapter.
"""
from __future__ import annotations

import math

JOINTS = ("shoulder_pan", "shoulder_lift", "elbow_flex", "wrist_flex", "wrist_roll", "gripper")
SERIAL = "5AE6075066"
CAL_ID = "2a1b5cc1-8e89-457e-8828-4d6d065f4ca6"
_CAL_FIELDS = {"id", "drive_mode", "homing_offset", "range_min", "range_max"}
_MAX_FRAMES = 100_001


def _number(value, name, *, positive=False):
    if type(value) not in (int, float):
        raise ValueError(f"{name} must be a finite number")
    try:
        value = float(value)
    except OverflowError:
        raise ValueError(f"{name} must be a finite number") from None
    if not math.isfinite(value):
        raise ValueError(f"{name} must be a finite number")
    if positive and value <= 0:
        raise ValueError(f"{name} must be positive")
    return value


def _raw_pose(pose):
    if not isinstance(pose, dict) or set(pose) != set(JOINTS):
        raise ValueError("A pose must contain exactly the six standard joint names")
    if any(type(pose[name]) is not int or not 0 <= pose[name] <= 4095 for name in JOINTS):
        raise ValueError("Pose positions must be raw integers in [0, 4095]")
    return {name: pose[name] for name in JOINTS}


def validate_calibration(cal):
    """Return a copied six-joint calibration; reject malformed IDs and raw ranges."""
    if not isinstance(cal, dict) or set(cal) != set(JOINTS):
        raise ValueError("Calibration must contain exactly the six standard joints")
    result = {}
    for motor_id, name in enumerate(JOINTS, 1):
        item = cal[name]
        if not isinstance(item, dict) or set(item) != _CAL_FIELDS:
            raise ValueError(f"Invalid calibration fields for {name}")
        if any(type(value) is not int for value in item.values()):
            raise ValueError(f"Calibration fields for {name} must be integers")
        if item["id"] != motor_id or item["drive_mode"] not in (0, 1):
            raise ValueError(f"Invalid motor ID or drive mode for {name}")
        if not 0 <= item["range_min"] < item["range_max"] <= 4095:
            raise ValueError(f"Invalid calibrated raw range for {name}")
        result[name] = dict(item)
    return result


def validate_pose(pose, cal, margin=32):
    """Return a copied raw pose within every calibrated range and its margin."""
    if type(margin) is not int or margin < 0:
        raise ValueError("margin must be a nonnegative integer")
    calibration, result = validate_calibration(cal), _raw_pose(pose)
    for name in JOINTS:
        low = calibration[name]["range_min"] + margin
        high = calibration[name]["range_max"] - margin
        if low > high or not low <= result[name] <= high:
            raise ValueError(f"Pose joint {name} is outside the calibrated margin")
    return result


def interpolate_pose(start, end, progress):
    """Quintic interpolation with exact integer endpoints; never wrap an encoder."""
    first, last = _raw_pose(start), _raw_pose(end)
    t = _number(progress, "progress")
    if not 0 <= t <= 1:
        raise ValueError("progress must be in [0, 1]")
    if t == 0:
        return first
    if t == 1:
        return last
    weight = max(0.0, min(1.0, t * t * t * (10 + t * (-15 + 6 * t))))
    return {name: round(first[name] + weight * (last[name] - first[name])) for name in JOINTS}


def plan_waypoints(points3, cal, segment_s=15.0, hz=10.0, max_speed=80.0, max_step=8):
    """Plan point 1→2→3 only; reject excessive speed/steps rather than rescale.

    The continuous quintic velocity bound is 1.875 * abs(delta) / segment_s.
    Rounded commands must independently satisfy max_step. No initial approach,
    return-to-start, calibration mutation, inverse kinematics or collision test
    is performed. Limits are explicit inputs; the adapter pins approved values.
    """
    if not isinstance(points3, (list, tuple)) or len(points3) != 3:
        raise ValueError("Exactly three poses are required")
    segment_s = _number(segment_s, "segment_s", positive=True)
    hz = _number(hz, "hz", positive=True)
    max_speed = _number(max_speed, "max_speed", positive=True)
    if not math.isfinite(2 * segment_s):
        raise ValueError("Total duration must be finite")
    if type(max_step) is not int or max_step <= 0:
        raise ValueError("max_step must be a positive integer")
    intervals = segment_s * hz
    if not math.isfinite(intervals) or not 1 <= intervals <= (_MAX_FRAMES - 1) // 2:
        raise ValueError("Requested frame count is outside the bounded planning limit")
    steps = round(intervals)
    if not math.isclose(intervals, steps, rel_tol=0.0, abs_tol=1e-9):
        raise ValueError("segment_s * hz must be a whole number of intervals")
    points = [validate_pose(point, cal) for point in points3]
    peak_speeds = []
    for first, last in zip(points, points[1:]):
        if abs(last["wrist_roll"] - first["wrist_roll"]) > 512:
            raise ValueError("Wrist segment exceeds 512 raw counts; wrapping is prohibited")
        peaks = {name: 1.875 * abs(last[name] - first[name]) / segment_s for name in JOINTS}
        if any(speed > max_speed for speed in peaks.values()):
            raise ValueError("Segment exceeds the configured continuous speed bound")
        peak_speeds.append(peaks)
    frames = [{"offset_s": 0.0, "positions": dict(points[0])}]
    observed_steps = {name: 0 for name in JOINTS}
    for segment, (first, last) in enumerate(zip(points, points[1:])):
        for step in range(1, steps + 1):
            pose = interpolate_pose(first, last, step / steps)
            previous = frames[-1]["positions"]
            for name in JOINTS:
                difference = abs(pose[name] - previous[name])
                if difference > max_step:
                    raise ValueError("Rounded commands exceed the configured step bound")
                observed_steps[name] = max(observed_steps[name], difference)
            frames.append({"offset_s": (segment * steps + step) / hz, "positions": pose})
    return {
        "schemaVersion": 1, "serial": SERIAL, "calibrationId": CAL_ID,
        "class": "software_planned", "physical_verified": False,
        "collision_checked": False, "interpolation": "quintic_joint_space_raw_no_wrap",
        "inputposes": points, "frames": frames, "duration_s": 2 * segment_s,
        "segment_s": segment_s, "hz": hz, "segment_peak_speed_counts_s": peak_speeds,
        "max_speed_counts_s": {name: max(peak[name] for peak in peak_speeds) for name in JOINTS},
        "observed_max_step_counts": observed_steps,
        "limits": {"margin_counts": 32, "max_speed_counts_s": max_speed,
                   "max_step_counts": max_step, "max_wrist_segment_counts": 512},
        "initial_approach_included": False, "return_to_start_included": False,
    }

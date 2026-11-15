# Read-only M08 calibration audit

Both current LeRobot calibration files exist and exactly match the current native Studio records. **The existing IDs, file paths, robot types and unit settings are now established from saved configuration.** This does not establish full-arm teleoperation readiness. Audit by `/root/reconcile`, session `966c1caf-f8f1-4221-87e7-85c67748c871`, observed at **2026-11-15T07:41:50.464941+00:00**; designated reporter `/root/shared_sync`.

The owner confirmed the replacement controller during this task: **leader `5B91027633`, follower `5AE6075066`**. Earlier leader `5B91030668` and its null calibration remain historical. A saved-metadata GET at **07:38:21.736598 UTC on November 15, 2026** returned the replacement registration and both six-joint maps. [Exact response](native-studio-robots.raw.json) and [request scope](native-studio-robots-read.json) are preserved. No online probe, Identify, observation stream or connect endpoint was used.

| Setting | Follower | Replacement leader |
| --- | --- | --- |
| Existing LeRobot ID | `2a1b5cc1-8e89-457e-8828-4d6d065f4ca6` | `13b35ac4-c088-4441-bfc9-c53987742388` |
| CLI type selector | `so101_follower` | `so101_leader` |
| Runtime calibration directory class | `robots/so_follower` | `teleoperators/so_leader` |
| Saved `use_degrees` | `false` | `false` |
| Stable port serial | `5AE6075066` | `5B91027633` |
| Calibration file SHA-256 | `7fc283b68be9c0e7117b140ed532f6ef865c4cf6cef89182a3e3a972772ef968` | `d4ce6723bc2674eb63425fb3908d8b9c5c0488c89e78ed9080b91d9c71fa8e49` |

The exact configurations are `/home/intel/project-morph/morph-robot/morph-robot-lerobot/.runtime/follower-lerobot-config.json` and `leader-lerobot-config.json`. Both specify absolute `calibration_dir` values beneath `/home/intel/project-morph/morph-robot/morph-robot-lerobot/.runtime/lerobot/calibration`, with a file named `<id>.json`. Their IDs happen to match Studio UUIDs, but this audit establishes them from the existing CLI files and receipts rather than assuming an identity convention.

The standard `/home/intel/.cache/huggingface/lerobot/calibration` directory is empty. The project explicitly configures `HF_LEROBOT_HOME` to its `.runtime/lerobot` directory. No calibration is missing from that actual project location. Only allowlisted cache/calibration settings were retained from private environment configuration.

The standalone environment contains LeRobot **0.7.0/Python 3.12**; the native Studio environment contains LeRobot **0.6.0/Python 3.13**. Source reads show the standalone SO follower/leader classes default `use_degrees` to `true`; preserve the existing explicit `false` on both sides. That selects body positions in **[-100, 100]**, with the gripper in **[0, 100]**, matching the inspected Studio normalized conversion. No driver objects were constructed.

All twelve joint entries match the current Studio maps exactly and satisfy the five-field integer calibration schema with IDs 1–6 and ordered ranges. The follower save receipt at **01:07:21 UTC** and replacement-leader receipt at **06:11:53 UTC** match the current file hashes. The other session's saved **07:36:08 UTC** snapshot matches all **36 homing-offset/minimum/maximum values**, reports no register writes and closed ports at the end. This is attributed historical motor evidence; this audit did not repeat those reads.

The earlier 22:31:55 UTC record is preserved: its follower values differ from the current map, and its leader was the previous controller. New saved calibration evidence supersedes that inventory without retroactively changing it.

Physical acceptance remains open. The replacement save receipt explicitly keeps full-arm following and sustained voltage-fault resolution unverified. The later bounded zero-status snapshot does not prove either. Both wrist maps retain the full encoder range 0–4095, while the replacement receipt records a limited observed cable arc and no verified full-rotation safety. Operator readiness, exclusive port ownership, supported poses, agreed motion limits and the stop method must be settled before motion. The official CLI may configure motors or enter calibration when connecting; file equality is not permission to run it.

Full measurements, exact paths, unit findings and remaining gates are in [calibration-audit.json](calibration-audit.json), with [input hashes](input-hashes.json). No calibration, configuration, source, runtime or historical evidence was modified. Root owns the single proposed command and readiness conversation; `/root/shared_sync` owns the combined verified report.

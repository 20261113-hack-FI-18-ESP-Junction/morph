# Three-point follower I/O test review

Agent `/root/reconcile` independently reviewed the follower CLI and authored [29 fake-bus tests](../../../tests/test_so101_three_point_io.py). All 29 passed at **2026-11-15T07:54:04Z** in 0.088 seconds. The CLI, planner and both test files were unchanged during this run. [test-results.json](test-results.json) records exact source hashes, command, timestamps, result and output hashes; [unittest.stderr.txt](unittest.stderr.txt) preserves the full test output.

The runtime CLI belongs to `/root`; the pure planner and its separate tests belong to `/root/dashboard`. This review changed only the I/O test file and this evidence directory. It neither reran the already-passed planner tests nor edited another agent's runtime code. Designated reporter `/root/shared_sync` receives this complete attributed contribution for the combined M08 update; remote delivery remains pending until its write/read-back receipt is confirmed.

The fake bus applies writes before injecting lost acknowledgments, models the observed possibility that a goal write energizes a motor, and uses a deliberately stale preexisting goal. The tests verify:

- Teaching saves three measured fake poses, never writes a goal or enables torque, retains partial point evidence after interruption, and rejects calibration changes between points or before the complete record is saved.
- Offline planning never constructs or resolves a bus. Missing readiness, changed identity/calibration/units, malformed schema, duplicate JSON keys and nonfinite JSON values are rejected.
- Preflight rejects mismatched configuration, motor alarms and stale telemetry without repairing configuration. Replay rejects a distant start or an already powered arm before any register write.
- A failed exclusive-open phase still closes the simulated port. Partial RAM initialization and lost goal acknowledgments lead to attempted torque-off for every motor, followed by verification and only the known saved RAM restoration.
- Cleanup continues after individual motor failures, reports unverified torque or failed closure, rechecks torque after RAM restoration, retries torque-off if it changed, and never restores old goals or prior enabled torque.
- Out-of-allowlist, calibration-margin and excessive-step writes are rejected. Calibration changes after hold prevent route commands. The approach starts at each actual hold goal after small passive drift. A complete fake route preserves operator observation as pending and restores RAM only after torque-off.

No blocking source finding remains from this bounded review of the tested version. These tests use synthetic temporary calibration, mocked time and input, and an injected in-memory bus. They do not open hardware, import LeRobot's bus implementation, use Studio or providers, or modify actual calibration/configuration. Real serial ownership and signal interruption are mocked; physical response, calibration provenance, path clearance and firmware timing are untested here.

Operator readiness is still required before teaching, including physical support before torque release. Replay is a separate operation after reviewing the three captured positions and confirming a clear path, a nearby start and a physical power cutoff. The successful fake route is not physical calibration or replay acceptance. The nominal route is 30 seconds plus a one-second nearby approach; synchronous I/O adds wall time, which the CLI records separately under its 60-second replay alarm.

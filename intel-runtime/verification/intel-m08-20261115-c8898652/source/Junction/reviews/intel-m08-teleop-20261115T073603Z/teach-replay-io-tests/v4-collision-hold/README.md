# Collision replay hold verification

**Replay is blocked in the current CLI.** Agent `/root/reconcile` verified the root-authored hold without changing the runtime source. All **65 tests passed at 2026-11-15T08:12:32Z**, in 0.373 seconds: five new tests of the real collision gate, 42 historical fake-bus control regressions and 18 pure planner tests. Source hashes before and after the run match. See [test-results.json](test-results.json) and the complete [unittest.stderr.txt](unittest.stderr.txt).

The five `ReplayHoldTests` leave `require_replay_clearance()` unpatched. They verify that:

- `main` returns the collision stop with missing input and calibration, without entering data validation or creating a journal.
- `--operator-ready`, three repeats and start point 3 cannot bypass the hold.
- The hold precedes duration validation and journal creation even when the duration is invalid.
- No calibration read, teaching load, planning call, journal construction, timer setup, serial resolution, bus construction or follower access occurs.
- Direct calls to `replay` fail before reading calibration or calling any follower method. The clearance function unconditionally requires physical inspection and a separately reviewed path.

The old I/O test class is now explicitly named `HistoricalFollowerIOTests`. It mocks the gate only inside its injected-bus setup, with a clear source comment, so previously implemented control and cleanup paths retain regression coverage. Those tests do not enable the real CLI, authorize replay or establish table clearance. The independent gate tests exercise current blocked behavior.

The current blocked CLI SHA256 is `0da4ee3f411c74d6c5ecc5a18df15a6dba41e2ec5dd5f3906adede0e86a35baa`. The actual aborted replay used historical source SHA256 `1fd43e2395c0f8ce74877d01110545d6add2d82ea4c09d2d42478593c6e122b6`; the new source must not replace that historical identity. The collision report and unchanged original journal measurements are recorded in the separate [physical replay audit](../../physical-results/replay-evidence-summary.json).

This agent changed only its I/O tests and this new evidence directory. It performed no hardware access, replay, calibration/configuration change or physical inspection. Power-off confirmation and damage assessment are outside this software result. The hold has no command-line override; removing it requires a separately reviewed code change after physical inspection and path clearance. An instruction to return the arm does not change this software hold.

**The owner explicitly stopped further experiments.** This record closes the existing incident and software-hold evidence; no readiness request, retry or hardware operation is pending.

The complete attributed result was sent to `/root` and designated reporter `/root/shared_sync`. Remote delivery remains pending the reporter's verified write/read-back receipt. Earlier v1–v3 reports and physical evidence are preserved.

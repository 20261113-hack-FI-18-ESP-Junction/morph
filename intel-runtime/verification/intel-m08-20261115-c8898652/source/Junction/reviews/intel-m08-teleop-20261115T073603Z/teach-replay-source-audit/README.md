# Follower-only three-position teach/replay source audit

The installed LeRobot **0.7.0** motor API can support explicit raw-position capture and bounded replay, but the packaged robot project has no three-point teach/replay command. Existing follower hold/jog diagnostics provide useful guard, receipt and cleanup patterns. This is advisory source review by `/root/reconcile` at **2026-11-15T07:46:38.664846+00:00**; no driver was instantiated, hardware opened, test rerun or source changed.

The scope is now **follower `5AE6075066` only**. The previous leader teleoperation proposal is superseded. The existing follower ID is `2a1b5cc1-8e89-457e-8828-4d6d065f4ca6`, with calibration SHA-256 `7fc283b68be9c0e7117b140ed532f6ef865c4cf6cef89182a3e3a972772ef968`.

The actual motor class is `SerialMotorsBus`; `FeetechMotorsBus` is a deprecated compatibility alias. Use raw reads/writes with `normalize=False` when preserving taught encoder ticks. `connect(handshake=False)` skips the model/firmware handshake but opens the hardware at 1,000,000 baud with a 50 ms transport timeout. It must remain behind explicit capture/replay authorization and identity/ownership checks.

Several details materially affect implementation:

- Existing project diagnostics record that `Goal_Position` writes energize STS servos, including a same-position seed. Teaching must never send a goal. Before playback, require manual return near the first taught pose; reject a distant starting pose instead of jumping back from point three.
- `read`/`sync_read` do not necessarily raise on non-refusal alarm bits. Explicitly inspect `Status` and the actual mode, torque, positions and relevant health readings. Group position reads have bounded acquisition intervals, not guaranteed simultaneity.
- `write` is acknowledged; `sync_write` is not. Neither proves target convergence. A lost acknowledgment can follow an applied command, so mark cleanup required before the attempt and verify observed movement separately.
- `enable_torque`/`disable_torque` also change the Feetech EEPROM lock through `rustypot.set_torque`. A narrow explicit RAM write policy can use `Torque_Enable` directly with readback. The `torque_disabled()` context re-enables on exit and is unsuitable for teaching or fault cleanup.
- Preserve calibration and motor configuration. `is_calibrated` performs motor reads and ignores the calibration IDs when comparing names; validate identity separately. Configuration, calibration and motor setup calls do not belong in replay.
- Use all-joint explicit torque-off cleanup, continuing despite individual failures, followed by `disconnect(disable_torque=False)` in nested `finally`. Do not restore old goals or re-enable torque after an error. Cleanup cannot be guaranteed after process kill, lost power or bus failure; physical support and a local stop remain necessary.

A concrete implementation can save exactly three stable, timestamped six-joint raw poses linked to serial/UUID, calibration/configuration hashes and source version. Validate the complete file and candidate interpolation offline before any replay. Use bounded steps, speed and duration, no catch-up bursts, actual tracking checks and bounded endpoint settling. Capture and replay should be separate intentional operations; a complete capture is not a motion result.

Saved ranges are shoulder pan 736–3407, shoulder lift 817–3149, elbow 832–2992, wrist flex 884–3198, wrist roll 0–4095 and gripper 1926–3363. Those are encoder calibration bounds. The full wrist encoder range does not establish cable-safe rotation, and three hand-taught endpoints do not establish collision-free connecting paths. Do not interpolate through encoder wrap or auto-clamp an invalid point. Prior diagnostic choices such as a 32-count interior margin or an eight-count jog are evidence of that limited design, not authorization or validation for the new trajectory.

The [machine-readable audit](audit.json) contains exact method contracts, proposed acceptance checks and hashes for the inspected sources. `/root/dashboard` owns the parallel high-level recorder/replay review; root owns implementation scope and the operator readiness conversation. `/root/shared_sync` is the designated reporter. No independent publication was made.

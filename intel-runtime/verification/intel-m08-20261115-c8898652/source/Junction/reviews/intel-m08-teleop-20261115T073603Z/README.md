# M08: three follower points captured; table collision reported during replay

Session `966c1caf-f8f1-4221-87e7-85c67748c871`, Intel, November 15, 2026 UTC. **M08 remains In progress, with further physical replay blocked.** Three manually taught follower positions were saved. The subsequent authorized replay issued real position goals, and the operator reported that the robot collided with the table. The journal records a voltage-triggered abort before the first taught segment or any round completed. This was not a successful physical replay or an accepted M08 demonstration.

The operator's collision report and the recorded voltage stop are separate evidence. The impact time and any causal relationship between the collision and the voltage reading are unknown. The operator subsequently said the arm had been put back; that does not confirm motor power is physically off, adequate support is in place, or a damage inspection has passed. Root added a persistent replay hold to the current project CLI, with no command-line bypass. **The owner has now explicitly stopped physical experiments.** No further hardware action or readiness request is pending. No automatic retry, reuse of the archived executable, or loosening of voltage, position or speed guards is authorized. The current work is limited to preserving evidence, documenting the incident and completing shared reporting.

## Existing installation, identity and calibration provenance

The owner first requested a leader/follower teleoperation check, then confirmed that the leader was no longer available and selected follower-only manual teaching. The previously displayed official teleoperation command was **never executed**. Its installation and help checks remain dated evidence.

| Item | Observed installation |
| --- | --- |
| Standalone robot project | `/home/intel/project-morph/morph-robot/morph-robot-lerobot` |
| Existing interpreter | `/home/intel/project-morph/morph-robot/morph-robot-lerobot/.venv/bin/python`, Python 3.12.16 |
| Official upstream executable | `/home/intel/project-morph/morph-robot/morph-robot-lerobot/.venv/bin/lerobot-teleoperate`, LeRobot 0.7.0 |
| Official installed entrypoint | `lerobot.scripts.lerobot_teleoperate:main` |
| Separate native Studio environment | `/home/intel/project-morph/morph-ai/morph-physical-ai-studio/application/backend/.venv`, Python 3.13.18, LeRobot 0.6.0, Studio 0.3.0 |

Activation from any directory is `source /home/intel/project-morph/morph-robot/morph-robot-lerobot/.venv/bin/activate`; an absolute interpreter or executable needs no activation. The selected SO-101 upstream `--help` ran from **07:40:43.860181 to 07:40:48.187057 UTC**, returned zero, and produced 5,210 stdout bytes and no stderr after startup source review. It received no serial-port arguments and did not instantiate/connect a robot. Its stdout SHA-256 is `44ff2dc28a47f631558903791a93d73703a213a44c81ca0abbe7c9faf28a6def`. The [environment audit](environment/README.md) retains the supported flags and the superseded, unexecuted teleoperation proposal.

The follower is USB **5AE6075066**, stable path `/dev/serial/by-id/usb-1a86_USB_Single_Serial_5AE6075066-if00`, observed at `/dev/ttyACM0`. The owner confirmed replacement leader **5B91027633**, observed at `/dev/ttyACM1`, before removing it. Former leader `5B91030668` and its measurements remain historical. A transient process that held the replacement leader during preparation disappeared without this session stopping it. The [preparation ownership record](ports/ownership-preparation.json) records the later missing leader path; these are dated observations, not a continuing ownership guarantee.

The actual follower calibration ID is **`2a1b5cc1-8e89-457e-8828-4d6d065f4ca6`**. Its six-joint file is `/home/intel/project-morph/morph-robot/morph-robot-lerobot/.runtime/lerobot/calibration/robots/so_follower/2a1b5cc1-8e89-457e-8828-4d6d065f4ca6.json`, SHA-256 **`7fc283b68be9c0e7117b140ed532f6ef865c4cf6cef89182a3e3a972772ef968`**. The replacement leader's actual calibration ID is `13b35ac4-c088-4441-bfc9-c53987742388`. Both six-joint files matched the current saved native Studio maps. These IDs came from actual configuration, not assumptions about USB serials. Both teleoperation configurations explicitly use `use_degrees=false`; the new project tool uses raw encoder counts. See [calibration verification](calibration/README.md).

This M08 work preserved the existing environments, Studio source/database, saved calibration files and normalization settings. Authorized teaching and replay did perform the recorded motor RAM/torque/goal operations below; the installation and calibration preservation statements do not imply that the entire session was read-only.

## Teaching evidence: first refusal, then three saved points

The first authorized teaching command started at **07:55:52.570708 UTC** after supported-arm readiness confirmation. [teach-001.jsonl](teach-001.jsonl) records exclusive follower access, six configuration reads and one telemetry frame. It refused `elbow_flex=3034`, above the saved maximum 2992 and outside the retained 32-count margin. `shoulder_lift=820` was also close to its saved minimum 817; the margin requires at least 849. All six initial motor status values and torque-enable values were zero. Voltage was 11.9–12.0 V and temperature 30–34 C in this single snapshot.

That command aborted at **07:55:52.874312 UTC** before any register write, position goal or point capture. Cleanup completed at **07:55:52.908633 UTC** without errors. Its empty cleanup torque map must not be represented as six new readbacks: all-off evidence came from the initial telemetry, and no writes had occurred. The failed journal is preserved unchanged, SHA-256 `a30a470a7e80c495717f7db55b1ff73caca45e2ace1108366d0f22bc8d096430`.

After manual repositioning, the second command started at **07:57:35.881790 UTC** with a fresh [teach-002.jsonl](teach-002.jsonl). It explicitly disabled torque and captured all three stationary hand-positioned samples without sending `Goal_Position` or enabling torque. The resulting [three-points-001.json](three-points-001.json) was saved before offline planning ran. The following are the exact `captured_at` values in that saved file, rather than the slightly later journal event timestamps:

| Point | Stored capture time, UTC |
| --- | --- |
| 1 | `2026-11-15T07:58:29.820279+00:00` |
| 2 | `2026-11-15T07:59:23.471687+00:00` |
| 3 | `2026-11-15T08:00:43.153518+00:00` |

The teaching file is **1,105 bytes**, SHA-256 **`4966e65cc3d512090acd2bb84256c58d357b33489283a29072237e4a7956fe45`**. It records the follower serial, actual calibration ID/hash, `raw_encoder_counts`, and `physical_replay_verified=false`. Original joint vectors remain in the Intel-local file; the later failed replay does not change that original record to verified.

The default **15-second-per-segment** plan then rejected the saved points with `Segment exceeds the configured continuous speed bound` at **08:00:43.154570 UTC**. Thus three captures succeeded, but the overall second teaching command ended **aborted**, not fully successful. Cleanup at **08:00:43.195442 UTC** recorded all six joints torque-off and no errors; finish at **08:00:43.195618 UTC** recorded `cleanup_verified=true`. The second journal SHA-256 is `3c89a38254d9b1f92062a10a2fb5c31b7b2f32e02fbf10b8890cc5ba3eff87d4`.

Both teaching commands used the earlier CLI SHA-256 `464a743981eb3ab6101bed93b254df4ea10c8a8bcf17e5709fe90a15d255a2e3`, retained as [executed teaching source](executed-source/so101_three_point.py). That source is historical evidence and is not the current replay-blocked implementation.

## Reviewed software plan and its limits

[so101_three_point.py](../../scripts/so101_three_point.py) is project-authored software using the existing LeRobot low-level API; it is separate from the official upstream teleoperation CLI. Its [pure offline planner](../../scripts/so101_three_point_core.py) performs no hardware access. The [source audit](teach-replay-source-audit/README.md) records why teaching avoids position goals: a same-position `Goal_Position` can energize these STS motors.

The authorized playback was configured with **24-second segments**, starting at point 3 and repeating the forward/backward route for three rounds. [plan-repeat-001.json](plan-repeat-001.json), SHA-256 `5c88dca6307949f2782fcd6583f08191e524ab7f2690642f094e057ad281047e`, records:

- Route: **3 → 2 → 1 → 2 → 3 → 2 → 1 → 2 → 3 → 2 → 1 → 2 → 3**. Each round is 3 → 2 → 1 → 2 → 3; there is no direct point-3-to-point-1 closing shortcut.
- Twelve segments, **288 nominal route seconds**, 2,881 frames at 10 Hz. A separate one-second nearby approach makes **289 nominal seconds** including approach. Command/read overhead can extend wall-clock time; the adapter does not send bursts to catch up.
- A start within 32 raw counts of the selected point, exact taught endpoints, a 32-count calibrated margin, peak planned speed at most 80 counts/second, per-command changes at most eight counts, and each wrist segment at most 512 raw counts. Interpolation does not wrap angles.

The saved plan is `software_planned`, `physical_verified=false`, and `collision_checked=false`. It interpolates joint encoder positions; it has no table geometry, Cartesian collision model, or proven clearance between the endpoints. **The subsequent table collision demonstrates that those joint-space bounds did not establish a clear physical path.** The longer segment duration was an explicitly reviewed change after the speed rejection, not an automatic weakening of the speed guard.

The executed adapter retained the diagnostic voltage guard **11.5–12.2 V** and temperature limit below 45 C, along with status, tracking, timing, torque and configuration checks. Those voltage/temperature values are local diagnostic limits, not manufacturer ratings. During replay it applied bounded RAM speed/acceleration settings; cleanup restored the saved RAM values only after verifying torque off and did not restore old position goals, enabled torque or EEPROM calibration. Successful software cleanup does not establish an independently tested physical emergency stop or prevent gravity motion.

The [pre-replay combined test run](teach-replay-io-tests/v3-supervised-repeat/README.md) passed **60 tests: 18 planner and 42 I/O tests**, at **08:05:20 UTC**, with source hashes unchanged before/after. The tests covered malformed inputs, bounds, interpolation, exact repeat-route endpoints/timing, no input mutation, distant starts, alarms, communication/readback failures and cleanup through an injected fake bus. The tested CLI hash was `1fd43e2395c0f8ce74877d01110545d6add2d82ea4c09d2d42478593c6e122b6`; planner hash was `78a2fde8cbe67a0cb17bf692b72b5bf8c8e5cfed44f8314a3dd9f8b16e71fe62`. Earlier test totals are separate development snapshots and are not added to 60. These tests did not establish real table clearance, firmware behavior, physical collision response or successful replay. The later persistent replay hold changes the current CLI; its separate validation must not be attributed to this earlier 60-test run.

## Historical physical replay and observed failure

The following is the **exact already-executed command**, retained for traceability. It is not a current instruction. Do not rerun it or invoke the archived source to bypass the current hold.

```bash
/home/intel/project-morph/morph-robot/morph-robot-lerobot/.venv/bin/python /home/intel/Documents/Junction/scripts/so101_three_point.py replay --input /home/intel/Documents/Junction/reviews/intel-m08-teleop-20261115T073603Z/three-points-001.json --journal /home/intel/Documents/Junction/reviews/intel-m08-teleop-20261115T073603Z/replay-001.jsonl --segment-s=24 --repeat=3 --start-point=3 --operator-ready
```

[replay-001.jsonl](replay-001.jsonl) started at **2026-11-15T08:07:32.680380+00:00**. Its recorded CLI hash is **`1fd43e2395c0f8ce74877d01110545d6add2d82ea4c09d2d42478593c6e122b6`**, matching the pre-replay tests. Exact executed copies of the [adapter](executed-source/replay-001/so101_three_point.py) and [core](executed-source/replay-001/so101_three_point_core.py) are preserved separately from the new hold. The 148,792-byte journal, with 594 JSON lines, is unchanged at SHA-256 **`cde6841eed9b69d90e4a1a56c4a5bd11755fb8f2943db77aee8c89c612330cbd`**.

The independent [replay evidence summary](physical-results/replay-evidence-summary.json) establishes the following measured limits:

- **480 logged `Goal_Position` attempts**, arranged in 80 complete six-joint groups: one initial hold, ten nearby-approach groups, and 69 taught-route frames. The last issued route frame was at nominal offset **6.9 seconds**, within the first **point 3 → point 2** segment. **Zero taught segments and zero rounds completed.** A `write_attempt` is logged before the individual bus write; it is not itself an acknowledgment receipt. Later control flow and telemetry show real progress through the sequence.
- Initial-to-last recorded encoders changed on `shoulder_lift` from 1911 to 1988 (**+77 raw counts**) and on `elbow_flex` from 1585 to 1614 (**+29**). The other four first/last values were unchanged. This confirms encoder movement, not Cartesian clearance or task success. The largest recorded difference from the most recent goal was three counts.
- At **08:07:42.608662 UTC**, the final telemetry read gripper voltage **114 raw = 11.4 V**, below the retained **11.5 V** lower guard. All 546 motor-status observations across 91 telemetry frames were zero. Recorded temperatures were 30–39 C. Zero motor-status values did not establish absence of contact or collision.
- The adapter logged its voltage-guard abort at **08:07:42.608878 UTC**. No position goal was logged after that abort. Cleanup at **08:07:42.657339 UTC** recorded all six expected joints torque-off, `completed=true`, and `errors=[]`. Finish at **08:07:42.657456 UTC** recorded `outcome=aborted` and `cleanup_verified=true`.

The hash-matched cleanup source attempts all six torque-off writes before readback, restores only saved RAM speed/acceleration after all-off verification, verifies torque again and closes using `disconnect(disable_torque=False)`. The cleanup record summarizes these results; individual cleanup register values and port closure are not separate journal events. No new hardware check was performed by the documentation or evidence-audit agents.

The owner subsequently reported **“The robot collided with the table.”** This is direct operator evidence, recorded separately from the journal. The record has no contact sensor or timestamped impact event, so neither the time of impact nor the direction of causality between impact and the voltage reading is established. Do not diagnose a power supply, cable or controller fault from this record alone. The owner's later statement that the arm was put back does not confirm physical power isolation, lack of damage or readiness for another motion.

## Current replay hold and remaining acceptance

Root's current adapter calls `require_replay_clearance()` before calibration-file access, journal creation or serial opening in the replay CLI path, and again before follower access in the replay function. It unconditionally rejects replay and offers no CLI override. This persistent hold is a software restriction; it is not evidence that motor power was physically removed. The [separate hold validation](teach-replay-io-tests/v4-collision-hold/README.md) passed **65 tests at 08:12:32 UTC**: five tests exercise the actual unpatched gate, 42 preserve historical fake-bus control regressions, and 18 test the pure planner. The real gate rejects even with `--operator-ready`, before calibration or teaching reads, planning, journal creation, timer setup, serial resolution or follower access. Only the historical injected-bus regression class mocks the gate; this does not enable the real CLI. The current blocked CLI SHA-256 is **`0da4ee3f411c74d6c5ecc5a18df15a6dba41e2ec5dd5f3906adede0e86a35baa`**. Its historical executed counterpart remains `1fd43e2395c0f8ce74877d01110545d6add2d82ea4c09d2d42478593c6e122b6`; the original journal is unchanged.

The owner explicitly stopped physical experiments after the collision. There is no next hardware action, retry or pending readiness request in this session. Physical power isolation/support, damage inspection, impact timing and path clearance remain unverified facts; they are not an instruction to perform another test. The original endpoint/rate review was insufficient. Keep the existing voltage and motion limits, retain the replay hold and do not execute the archived source. If the owner initiates a separate future hardware task, it will require fresh, specific authorization, physical inspection and an explicitly reviewed path with table clearance. Only offline source review, incident documentation and reporting continue now.

M08 remains **In progress** with open acceptance. This failed follower-only replay does not establish leader/follower teleoperation, a learned skill, policy training, task-suitable camera operation, complete start/pause/stop behavior, or a tested physical emergency stop. The original teaching samples, both teaching journals, plan and failed replay remain preserved as evidence, including their limitations.

## Attribution and synchronization state

`/root` owns the operator discussion, actual authorized hardware commands, adapter implementation, persistent replay hold and root-level project status. `/root/dashboard` audited the existing environment/official help, implemented and tested the pure offline planner, and reconciled this report from the saved evidence. `/root/reconcile` audited calibration and low-level source, authored independent I/O tests, and produced the read-only replay analysis. `/root/shared_sync` is the designated reporter for all four contributions. This report update performed no hardware operation and edited only this README.

The initial preparation and changed-scope notes were confirmed on the shared Mac. The collision correction **`ec21a94c-793b-4b59-bbbf-102af8d624bc`** was saved/read back at **08:10:55.932878 UTC**, SHA-256 `4fd71ac51513be41fe1d86f3b3b8755e5fb92af7b33eb0b44c4f8f0d01523aef`; [its receipt](shared-sync/checkpoint-5-ordinary-receipt.json) records no new work event. It supersedes the earlier pending-operator-observation statement. Final combined source, completed hold validation and this updated report remain subject to the reporter's separate confirmed delivery; a local file or progress-note receipt does not prove source reconstruction, Mac review, publication or deployment.

The latest independently fetched [Notion confirmation](shared-sync/notion-checkpoints-1-2-confirmed.json) covers the first two updates through the **07:57:48.121 UTC** Mac readback. M08 was **In progress**, with its acceptance checkboxes open. That dated confirmation does not cover the later captures, replay, collision or persistent hold. Their Notion reconciliation remains pending, tracked separately from shared-note delivery. Mac recurring reviews are owner-paused; do not infer a future automatic review or restart the revoked Intel receiver.

The authorized source group includes eligible implementation, tests and English documentation with frozen hashes. Original calibration/runtime files, raw taught vectors and motor journals remain Intel-local under the sender's exclusions; source review receives sanitized summaries and exact evidence hashes. Preserve confirmed, pending, received, reviewed, published and deployed states separately in the [delivery report](shared-sync/DELIVERY_REPORT.md).

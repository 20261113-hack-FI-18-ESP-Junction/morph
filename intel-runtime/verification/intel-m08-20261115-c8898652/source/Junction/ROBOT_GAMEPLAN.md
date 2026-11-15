# Morph / LeRobot: hardware verification and training plan

Updated on November 15, 2026. This record belongs to `/home/intel/Documents/Junction`; the historical application checkout is `/home/intel/physical-ai-studio`. See the current M08 review for the active standalone LeRobot and native Studio locations. Times below are local to `America/Los_Angeles` unless stated otherwise. All project documentation and newly authored file content must be in English.

## Current position

**November 15, 2026 UTC M08 update:** the owner confirmed replacement leader controller `5B91027633`, then removed the leader and requested manual three-point teaching and replay of follower `5AE6075066`. The official leader/follower CLI command was prepared but never executed. The existing standalone runtime is LeRobot 0.7.0; both actual calibration files were found and matched the saved Studio records. Three follower points were captured with torque off after the owner repositioned the arm. The first attempt at 07:55:52 UTC had stopped before writes on an out-of-range elbow; the subsequent successful capture and default-speed planning rejection remain separate evidence.

**Table collision during authorized playback:** the three-round, 24-second-per-segment replay began at 08:07:32 UTC. The owner reported a collision with the table. No segment or round completed; only the first 6.9 nominal seconds of the initial 3-to-2 route segment were commanded. At 08:07:42.608878 UTC the software stopped on a gripper reading of 11.4 V, below its retained 11.5 V guard. Collision timing and voltage causality are unknown. Cleanup verified all six motors torque-off and port closure at 08:07:42.657339 UTC. The owner then reported putting the arm back; physical power disconnection and damage inspection remain unconfirmed.

The owner explicitly stopped the experiments after putting the arm back. No further hardware attempt is authorized in this session. The current helper blocks replay before serial access and offers no CLI override; all 65 subsequent software tests passed, including five checks of the actual hold. The 60 tests for the earlier executed version verified software behavior, not table clearance. Preserve the three points, original journals, calibration and exact executed sources. Any future resumption requires a separate owner instruction, physical inspection and a new path reviewed for table clearance. Do not use a relaxed voltage threshold or an automatic repeat as a collision recovery. The [M08 report](reviews/intel-m08-teleop-20261115T073603Z/README.md) contains evidence and shared-reporting state. M08 stays In progress; follower replay does not fulfill the original leader/follower teleoperation criterion.

**November 15, 2026 UTC source continuation:** the remaining source request `90672035-350b-43ad-88d6-025885cfbd65` follows the completed Jose delivery. Current dashboard/client/analyst and Intel tooling are compared against the supplied Mac baselines and transferred through the unchanged sender in separate verified groups. See the [delivery ledger](reviews/source-supplement-20261115T031731Z-90672035/DELIVERY.md) for actual results and exclusions. The physical execution order and the owner's control of arm diagnostics remain unchanged; source receipt does not establish deployment or physical acceptance.

**November 15, 2026 UTC takeover priority:** Jose receives Intel's current control inventory and focused source before broader packaging. The current Morph station has no integrated mission/control API or hardware dispatcher; its command and voice endpoints return 503. Record-session start/end must not be presented as robot mission control. Jose owns interaction/coordination and expected voice input, with ElevenLabs undecided; Klemen owns the dashboard, and Intel retains local validated execution and authoritative records. The NVIDIA tunnel is supplied by the other team. The [takeover report](reviews/jose-takeover-20261115T022548Z-00e34e99/README.md) records source delivery and the remaining implementation boundary. This handoff does not change the owner's arm-diagnostics ownership or complete any physical prerequisite.

**November 14, 2026, 22:32 UTC update:** the Mac offline audit is integrated into the current Intel station with all 58 original audit tests, three required CLI checks and the 230-test combined backend suite passing. Read the [integration report](reviews/mac-offline-evidence-20261114T222550Z-8941c757/INTEGRATION_REPORT.md), [ordered readiness review](reviews/mac-offline-evidence-20261114T222550Z-8941c757/execution-readiness.md) and [physical execution record](reviews/mac-offline-evidence-20261114T222550Z-8941c757/physical-execution-record.md). Continue environment/cameras/calibration, mentor and pilot decisions, real demonstrations/skills/Anomalib, a full physical cycle, the existing Intel Gemma integration, then M22 after the baseline works. The separate Mac control/provider/voice owner retains M12/M17/M18/M05/M19. These software results do not complete physical acceptance.

The saved Studio configuration at **22:31:55 UTC** contains six follower calibration entries and no leader calibration. This is stored metadata with unverified provenance; it does not supersede the earlier owner statement with a claim that calibration is physically complete. The environment still has no robot assignments, datasets or trained models. Preserve the stored values, reconcile their origin and validate the correct arm with the owner before using or changing them. Both Studio runtime registries were empty at 22:32:25 UTC; no camera or arm was opened for this integration.

The user confirmed that both arms are SO-101, each controller has its own connected power supply, and neither arm has been calibrated. The USB hub does not have an external power supply. Motor ID and baud-rate setup is separate from calibration. When asked, the user answered that they are not sure whether motor setup was done; record it as unknown and resolve it through evidence. Do not repeat that question or ask the user to reconfirm the established power arrangement.

The user prioritized cameras before further arm testing. Camera connection checks are now complete: the RealSense D415, webcam, and additional USB2.0_CAM1 each delivered images through Studio, both individually and concurrently, at 640 × 480 and approximately 29–30 frames/s. The RealSense and webcam produced clear views of the work surface. USB2.0_CAM1 produced a noticeably out-of-focus image and does not expose the standard V4L2 focus controls. These were short checks, not a demonstration of long-term stability.

The RealSense D415 already outputs computed Z16 depth. Its native test captured RGB, depth, and both infrared views together: 149 distinct frames per stream in approximately five seconds, with no missing frames or timeouts. On average, 89.56% of depth pixels were nonzero. That measures coverage, not depth accuracy. The reported depth-unit scale was approximately 0.001 m. No custom stereo-depth algorithm is needed; `scripts/check_realsense_depth.py` already verifies and saves this output.

The current Studio preview and demonstration recording use RGB. Displaying and recording metric depth in the application requires additional integration; the installed depth-video writer explicitly does not support it. The RealSense SDK serial is `243622061552`, which differs from its USB identifier listed below. Full results, tested settings, and saved images are in [the camera report](camera-check-2026-11-14/README.md).

The first concurrent preview attempt, immediately after closing earlier captures, encountered a RealSense publisher timeout. Once the earlier captures had fully shut down, starting all three cameras concurrently succeeded. Application code was not changed. Allow the previous capture process to finish when reopening a camera; the successful retry does not establish the exact cause of the first failure.

Both arm USB connections were accessible during the earlier probes, but motor communication was not verified: the tested motor IDs did not respond. A subsequent inventory at **2026-11-14T18:41:22.572916+00:00** (10:41:22 local time) enumerated only serial `5AE6075066`; serial `5B91030668` was absent from both host and container USB enumeration. The container still had a stale `/dev/ttyACM1` node. These are historical observations preceding the owner updates described below; the missing-device cause remains unproven. See [the historical USB inventory](usb-status-2026-11-14-documentation-update.json).

The user corrected the earlier reversed assignment, recorded at **20:43 UTC on November 14, 2026**: **leader `5B91030668`**, **follower `5AE6075066`**. The earlier role-based report that the follower works and the user is investigating leader communication follows these corrected serials. The user owns current arm diagnostics; coordinate before opening either serial port. This mapping correction does not establish new independent motor, calibration or teleoperation verification. No torque-enable commands, motion commands, motor configuration writes, or calibration have been performed by these diagnostics.

The newly imported `morph-intel-transfer/morph-context/` snapshot identifies this work as **Morph**, a Duplo quality-inspection and sorting workcell. Its November 14, 2026 requirements retain Studio/learned policies, Anomalib and supported OpenVINO execution, with Nemotron for frame-linked vision, Gemini for permitted task selection, and ElevenLabs for spoken commands. This replaces the earlier tentative proposal to use Nemotron as the task planner. Imported implementation and provider status are attributed to that snapshot; they are not new Intel-side verification. The architecture and source links are recorded below.

## Next practical steps

1. Incorporate the user's current leader communication findings, then recheck stable USB identity and establish exclusive port ownership before another agent connection. Keep the old missing-controller observation as serial-specific historical evidence; the earlier role-based working-follower report follows the corrected mapping.
2. Use bounded diagnostics or supplier evidence to resolve the unknown motor setup when needed. Preserve the corrected leader `5B91030668` and follower `5AE6075066` assignments. Motor setup is separate from calibration; roles do not follow from `/dev/ttyACM0` or `/dev/ttyACM1`. Coordinate physical connection changes with the user.
3. If communication remains absent, identify the controller model and inspect its documented communication mode. The SO-101 instructions discuss putting both Waveshare jumpers in position B for USB operation; that instruction applies only if the actual boards are Waveshare. The controller model is not yet confirmed.
4. Choose the next bounded motor diagnostic from the verified setup information. Preserve failure reports, avoid repeating identical unsuccessful checks without new evidence, and do not run motor setup on an entire assembled chain automatically.
5. After every expected motor responds and the operator, stop method and motion limits are established, carry out guided calibration with the user present. Then verify limited teleoperation before collecting demonstrations.
6. Use the working RealSense RGB view and webcam to prepare the first task views. Resolve the additional camera's focus only if it is needed. Metric-depth integration is a separate software task; the current RGB pipeline already supports the next camera-related preparation work.

## Verified environment and connections

These values describe the inspected environment on November 14, 2026; refresh device paths and live state before a future hardware operation.

| Component | Verified result |
| --- | --- |
| Physical AI Studio | Container `physical-ai-studio-xpu`; Docker and `/api/health` reported healthy. |
| Container Studio address | `127.0.0.1:7860`; separate from native Studio. |
| Native Studio registration | `127.0.0.1:3000`, project `Morph SO-101 Workstation`; corrected arm roles verified at 20:46 UTC. |
| Application version | `0.3.0`, revision `8f1324161ece2b24f2d38765b6e943ed1961258c`; matched the local checkout. |
| LeRobot and SO101 plugin | LeRobot `0.6.0`; SO101 plugin `0.3.0`. |
| PyTorch and GPU | `2.11.0+xpu`; `torch.xpu.is_available() == True`; Intel Arc B390. Squaring `[1, 2]` on XPU returned `[1, 4]`. |
| Container permissions | Supplementary groups include GID `20` (`dialout`); the container was already running with `privileged: true`. |
| Earlier container state at inspection | `/api/projects` returned an empty list. No projects, training jobs, or runtime sessions were active before the recorded container restart and hardware probes. |
| Calibration | No calibration JSON files were found in the mounted standard LeRobot directory. The user confirmed neither arm has been calibrated. Motor calibration registers have not been verified. |

The XPU calculation confirms basic accelerator operation. Policy training and inference have not been tested. The [dated native Studio correction report](morph-intel-continuation-20261114T193410Z/Morph-Intel-Handoff-20261114T191514Z/verification/intel-studio-role-correction-20261114T204500Z/README.md) separately verifies the registered project on port 3000 and empty container Studio on port 7860, with final read-back at 20:46:00.038 UTC. Inspect both instances before interpreting current application state; this documentation review made no new health request. The local application checkout already contains the user's change binding the web port to localhost and a `docker-compose.yaml.bak` file; preserve those changes.

| Device | Observed connection | Identifier |
| --- | --- | --- |
| SO-101 follower | Previously `/dev/ttyACM0`, USB `3-1.4.2`; working-follower report associated using corrected role | USB serial `5AE6075066` |
| SO-101 leader | Previously `/dev/ttyACM1`, USB `3-1.4.1`; absent at 18:41 UTC; leader communication report associated using corrected role | USB serial `5B91030668` |
| RealSense D415 | USB `2-2.4.4`, 5000 Mbit/s | USB identifier `344223023467`; SDK serial `243622061552` |
| Webcam Audio | USB `3-1.4.3`, 480 Mbit/s | USB ID `1bcf:0060` |
| Additional USB2.0_CAM1 | USB `3-1.3`, 480 Mbit/s | USB ID `05a3:9230` |

The arm connection record is [robot-connections.json](robot-connections.json). The earlier post-restart inventory is [usb-connected-2026-11-14.json](usb-connected-2026-11-14.json); [the 18:41:22 UTC inventory](usb-status-2026-11-14-documentation-update.json) records a later historical state. Both precede the owner's 19:47 UTC update. Device names such as `ttyACM0` and `ttyACM1` can change. Use serial numbers and current USB enumeration for identity, not a stale node. The container has no `/dev/serial/by-id` links, so use Studio's USB serial-number support when configuring arms.

For a repeatable inventory from this workspace:

```bash
python3 scripts/check_robot_usb.py --container physical-ai-studio-xpu
```

This script records system information and device paths without opening serial ports or capturing camera images. It also records video-node metadata, USB authorization, and power-management state. An inventory alone does not verify motor communication. Access visible to a restricted process may differ from the host or container, so compare the reported scopes.

## Motor communication results

On November 14, 2026 at approximately 09:39–09:40, bounded `scripts/probe_so101_readonly.py` checks ran sequentially on both arm ports. Before the checks, the application reported empty job and runtime-session lists, and the inventory confirmed the same two serial numbers.

- Both serial ports opened successfully at 1,000,000 baud using Feetech protocol 0.
- None of IDs 1–6 on either connection answered PING. The result was `[TxRxResult] There is no status packet!`.
- Position, voltage, and torque registers were not read in those probes because PING did not succeed.
- Both probes exited with a controlled failure after approximately 1.3 seconds and closed the ports using `disconnect(disable_torque=False)`.
- No motor registers were written, and there were no motion, calibration, or motor-ID setup commands.

The reports are [motor-probe-5AE6075066-2026-11-14.json](motor-probe-5AE6075066-2026-11-14.json) and [motor-probe-5B91030668-2026-11-14.json](motor-probe-5B91030668-2026-11-14.json). They establish a lack of replies at the tested IDs and speed, not broken motors or the absence of devices at every other address and speed.

Comparison with the installed Studio diagnostics confirmed the same bus class, baud rate, protocol, and IDs. Because Studio also reads voltage before PING, a separate direct read of `Model_Number` and `Present_Voltage` for IDs 1–6 ran on both ports at approximately 09:43. Each test waited one second after opening its port. All 12 reads on each connection again returned no status packet. Both ports were closed without motor-register writes. The reports are [motor-direct-read-5AE6075066-2026-11-14.json](motor-direct-read-5AE6075066-2026-11-14.json) and [motor-direct-read-5B91030668-2026-11-14.json](motor-direct-read-5B91030668-2026-11-14.json).

The user could not confirm whether IDs 1–6 and the required baud rate were configured on each arm. That state remains unknown. The official SO-101 workflow treats initial configuration of individual motors, assembly, and calibration as distinct steps.

## Diagnostic behavior that matters for further work

Studio's `Identify` action deliberately moves a joint or gripper. Opening the SO101 wizard also involves motor-bus access and connection cleanup; it is not a USB-only inventory. `lerobot-setup-motors` writes motor configuration and is not the initial communication check. Inspect connection and disconnection side effects in the installed version before selecting a motor diagnostic.

The inspected versions were LeRobot `0.6.0`, SO101 plugin `0.3.0`, Feetech SDK `1.0.0`, and pyserial `3.5`. The low-level `FeetechMotorsBus.connect(handshake=False)` opens the port without writing motor registers. Available operations include `ping()` and `read(..., normalize=False)` for `ID`, `Model_Number`, `Present_Position`, `Torque_Enable`, and `Present_Voltage`.

Cleanup for a register-read-only probe must explicitly call `disconnect(disable_torque=False)` in `finally`. Default disconnection writes `Torque_Enable=0` and `Lock=0`. Opening pyserial can change DTR/RTS, so even the low-level probe is not described as having no electrical side effects.

The high-level `physicalai_so101_plugin.SO101.connect()` writes motor configuration and torque settings. The follower's `disconnect()` in this plugin writes target positions and enables torque. Do not use that plugin as the initial register-read-only diagnostic. In the inspected version, SO101 `discover()` and `is_online()` only enumerate or compare ports. Only one process may own a serial connection during a motor test.

Inspected container sources under `/app/application/backend/.venv/lib/python3.13/site-packages/`:

- `lerobot/motors/motors_bus.py`
- `lerobot/motors/feetech/feetech.py`
- `physicalai_so101_plugin/so101.py`
- `physicalai_so101_plugin/studio_catalog.py`

The prepared `scripts/probe_so101_readonly.py` targets this environment, requires an explicit port, bounds execution time, and records errors. Its help output and read/cleanup behavior were checked with a substitute bus before the actual probes described above.

The script now also provides `--discover`, verified with ten software tests and not yet run on physical motors. It checks the installed LeRobot/SDK versions and supported STS3215 baud table, then performs broadcast PING and model reads for responding IDs at eight host baud rates. Each rate receives one second of settling; use `--timeout 30` when running the prepared mode after rechecking stable device identity and exclusive ownership. Host baud changes may reopen serial ports, but no motor configuration registers are written. Reports keep discovered IDs separate from the expected six-motor checks and do not claim chain completeness or calibration from a response.

## Historical USB investigation

This section preserves the initial observations. The complete absence of peripherals described here ended at approximately 09:26 on November 14, 2026. The later disappearance of one controller at 18:41:22 UTC is a separate observation recorded in the current-state section.

During the initial inspection, the restricted process, `/sys/class/tty`, and container showed no `ttyACM*` or `ttyUSB*` arm ports. USB hubs and a Synaptics device were visible, but the arm controllers were not identified. Absence from that inventory did not establish an arm failure.

The user confirmed both SO-101 arms, one stereo camera, and one webcam were physically connected through a USB hub, and subsequently confirmed that the hub had no external power supply. The hub model was not established. An additional USB2.0_CAM1 was identified later; the current inventory above lists the actual detected cameras.

At approximately 09:22:

- USB topology showed VIA and Realtek hubs without the arm controllers or external cameras downstream. USB 2 and USB 3 entries alone did not determine the number of physical hubs.
- The inspected kernel log contained hub discovery at 07:25 but no discovery of the four expected external peripherals. No overcurrent or USB-descriptor-read failures were found in that inspected log.
- Visible hubs were authorized (`authorized=1`), default USB authorization was enabled, and inspected ports had `disable=0` and `over_current_count=0`.
- Hubs reported `runtime_status=suspended`. This did not establish a cause, and power-management settings were not changed.
- All 32 system video nodes belonged to the PCI Intel IPU7 controller. They were not detections of the external USB cameras. The container could see those nodes, while the restricted process could not directly see `/dev/video*`.

A webcam test using a direct computer port or a known working data adapter was suggested to isolate the path, but execution of that physical test was not confirmed. The devices subsequently appeared, so it was no longer required to establish their presence. It remains a possible diagnostic if devices disappear again.

Between 09:26:54 and 09:26:57, the system detected both serial connections and the cameras. The cause of their earlier absence remains unconfirmed; the unpowered hub is not treated as proof of that cause.

The running container initially lacked the newly appeared `/dev/ttyACM*` nodes. After verifying empty project, training-job, and runtime-session lists, `docker restart physical-ai-studio-xpu` was executed. The application returned to a healthy state, and its user had read/write access to both serial devices through `dialout` (GID 20). Later camera captures established actual image delivery, as described above.

The initial inspection did not open motor buses. Subsequent bounded PING and direct-read probes are recorded separately. Existing configuration and calibration were not changed.

## Development stages and completion criteria

Camera connection verification was moved ahead of the arm stages at the user's request and has now passed with the limitations already recorded. Task-specific camera placement and synchronized demonstration recording remain future work.

| Stage | Work | Completion criteria |
| --- | --- | --- |
| 1. Arm identification | Preserve the corrected owner-confirmed roles and recheck stable USB identity before connection. | Both physical roles are unambiguously associated with accessible devices. |
| 2. Motor communication | Resolve initial setup uncertainty and perform bounded identity, position, and diagnostic reads using the inspected implementation. | Every expected motor responds with plausible position and diagnostic data. |
| 3. Calibration | Guide calibration of each arm; none has been completed yet. | Directions, ranges, neutral positions, and grippers are verified. |
| 4. Teleoperation | Let the leader drive the follower with limited initial motion and an available stop method. | The follower repeatedly and predictably follows leader motion. |
| 5. Task views and data | Set camera views and record 3–5 short trial demonstrations. Add depth capture support if the chosen workflow needs it. | Images, states, and actions are synchronized, and episodes save and replay correctly. |
| 6. Initial training | Choose the first Duplo inspection/sorting skill, collect suitable demonstrations, and separately train the Anomalib detector using independent reference labels. ACT is the initial policy baseline candidate, subject to the challenge requirements. | Training completes, policy outputs are checked against recorded observations, and detector quality is evaluated on the agreed data split. |
| 7. Policy execution | Conduct supervised short follower trials with defined starting states and limits. | Successes, failures, interventions, and inference latency are recorded. |
| 8. Adaptive integration | Add Nemotron visual observations, Gemini selection among permitted tasks, and finalized ElevenLabs voice commands through the validated local dispatcher. Assess GR00T separately only if needed. | One baseline cycle, one bounded recovery, and one supported spoken goal change have real evidence for each required integration. |

Before calibration and teleoperation, the user must be physically present at the arms and the work area must be understood. Establish the robot configuration, motion limits, and stop method before issuing the first motion commands.

## Imported Morph scope, model roles, and the current application

The imported project instructions and context were prepared on November 14, 2026, with the initial handoff labeled 17:25 CET (`Europe/Ljubljana`, UTC+01:00) and later dated implementation updates in individual files. They are a portable snapshot with their own history. Read current files before implementation and distinguish imported status from work verified on this Intel computer.

The selected workflow is a voice-directed Duplo inspection and sorting cell: observe, pick, verify grasp, present the brick to an inspection camera, inspect, select an allowed response, place it in the good or defective bin, and independently verify the outcome. The dashboard links each object to observations, measurements, decisions, attempts, and confirmed outcomes.

| Component | Role recorded in the imported requirements | Verification boundary |
| --- | --- | --- |
| SO-101, LeRobot, and Physical AI Studio | Demonstrations, learned manipulation policies, and controlled execution | Camera capture works locally; arm communication, calibration, demonstrations, training, and physical execution remain incomplete. |
| Anomalib | Defect measurements evaluated against independent reference labels | The later Intel continuation passed generated-image fit/export/CPU parity; useful real-brick detector training and evaluation remain open. |
| OpenVINO | Supported optimized inference on the target Intel system | Later Intel synthetic CPU/GPU checks passed; NPU, actual model quality and policy compatibility remain unverified. |
| NVIDIA Nemotron 3.5 Super VL | Visual observations linked to actual analyzed frames | The shared Mac reports accepted minimal access through Verda, M03 Done. Real Intel provider/frame integration remains unverified; preserve exact tested model/endpoint evidence. |
| Gemini `gemini-decision-1` through the Decisions API | Fixed-choice online task selection, bounded recovery, and operator goal selection | The shared Mac reports accepted minimal access, M04 Done. Intel integration remains unverified; it selects options rather than generating plans, explanations or function-call arguments. |
| ElevenLabs `scribe_v3_live` | Finalized spoken operator commands | M05 remains Blocked in the later Mac task audit; provider configuration, microphone/Scribe acceptance and venue-noise performance remain open. |

These later verification boundaries are documented in the [active Intel continuation](#active-intel-continuation--november-14-2026-after-1947-utc) and the [dated Mac provider/task handoff](mac-sync/initial-review/f823677fab02269534cd0173bf6770a4d6bf3e720a6616ba69cde485845f7405.json). They supersede the initial snapshot's unverified Mac-access statements without establishing new Intel provider success.

The earlier local sketch assigning task planning to Nemotron is superseded by this imported owner direction: Nemotron supplies vision, Gemini selects among allowed options, and the local application validates and dispatches a learned skill. Cloud models do not send joint commands. Preserve state/goal versions, evidence freshness, preconditions, timeouts, and duplicate-execution protection. Finalize and deduplicate a full spoken utterance before issuing a goal change; partial transcripts must not trigger actions.

The imported first demonstration target is one repeatable baseline cycle, one permitted bounded recovery, and one supported spoken goal change. Its M01–M24 task plan is the wider delivery plan; this file remains the Intel hardware/gameplan record. Our inventory and runtime work contribute to M02/M07, and the camera checks contribute to M08. **M08 is not complete from camera success alone:** calibration, teleoperation, and the actual stop procedure still need verification.

The imported `station/` documentation records M06 software acceptance and M15 dashboard/client work in progress. It explicitly states that robot, camera, and provider adapters are not connected. Those saved Mac software results are useful context, not fresh Intel acceptance or live Notion status. Local evidence and imported history must remain separately attributable.

Primary imported context:

- [Workspace requirements](morph-intel-transfer/morph-context/AGENTS.md)
- [Portable handoff](morph-intel-transfer/morph-context/context/START_HERE.md)
- [Selected workflow](morph-intel-transfer/morph-context/PHYSICAL_AI_WORKFLOW.md)
- [Orchestration contract](morph-intel-transfer/morph-context/PHYSICAL_AI_ORCHESTRATION.md)
- [M01–M24 task plan](morph-intel-transfer/morph-context/PHYSICAL_AI_TASK_PLAN.md)
- [Station implementation and verification boundary](morph-intel-transfer/morph-context/station/README.md)

At the earlier local inspection, Studio's `/api/policies/available` offered ACT, MolmoAct2, Pi0.5, RLDX-1, SmolVLA, and XR0. Nemotron and GR00T were not listed as robot policies. A provider's proposed orchestration or vision role is separate from this policy list. Appearance in the list is not evidence that a policy can be trained on this computer.

The previously inspected official LeRobot documentation describes **GR00T N1.7** with SO101, using NVIDIA/CUDA examples. Local Studio documentation for its GR00T wrapper describes an expected integration-test failure involving `flash_attention_2`; direct GR00T training on Arc B390 is not an established path. GR00T is a separate possible policy investigation and does not replace the required Nemotron contribution. Determine compatibility, requirements, and cost before any paid compute.

Inspected project references:

- `/home/intel/physical-ai-studio/application/docs/04-environment-setup.md`
- `/home/intel/physical-ai-studio/application/docker/docker-compose.yaml`
- `/home/intel/physical-ai-studio/application/backend/src/api/robot_catalog.py`
- `/home/intel/physical-ai-studio/application/backend/src/workers/robots/so101_setup_worker.py`
- `/home/intel/physical-ai-studio/application/backend/src/training/policy_catalog.py`
- `/home/intel/physical-ai-studio/library/docs/explanation/policy/lerobot.md`

Official web references inspected on November 14, 2026:

```text
https://huggingface.co/docs/lerobot/so101
https://github.com/huggingface/lerobot/blob/main/docs/source/so101.mdx
https://huggingface.co/docs/lerobot/groot
https://www.nvidia.com/en-us/ai-data-science/foundation-models/nemotron/
```

## Active Intel continuation — November 14, 2026, after 19:47 UTC

The [new handoff working copy](morph-intel-continuation-20261114T193410Z/Morph-Intel-Handoff-20261114T191514Z/INTEL_CONTINUATION.md) supplies the actual Morph React dashboard. Its Linux baseline build, 121 tests, HTTP checks and desktop/mobile browser checks passed on isolated simulation data. M16 adds audited review, late confirmation, history filters and read-only replay; the linked report records final acceptance. The older workspace, Studio volume/configuration, calibration mount and original camera/motor evidence were preserved.

The owner corrected the earlier assignment: **leader `5B91030668`**, **follower `5AE6075066`**. The prior role-based report says the follower works while the user investigates leader communication; its serial association follows this correction. Do not repeat the identity question or treat the earlier missing-controller inventory as the latest physical state. The user owns diagnostics at the arms; coordinate ownership before any serial operation. No new independent calibration, teleoperation or motor-read test was performed in this continuation.

An isolated Anomalib profile passed generated-image fit/export/CPU parity and a separate synthetic CPU/GPU OpenVINO check. NPU enumeration remains unavailable in both installed OpenVINO profiles. The resumed compatibility report identifies the missing standard NPU user-space component and a vendor candidate stack; exact host/shared-library/firmware/Studio compatibility still needs mentor review before a maintenance change. Actual brick data, model training and physical integration remain next gates. The Mac subsequently verified Nemotron/Decision 1 access with synthetic/minimal requests; Intel preflight still finds Decision 1, Verda and ElevenLabs credentials missing. Real provider integration and ElevenLabs microphone/Scribe acceptance remain open.

Continue by accepting the user's leader diagnostic result, establishing the real operator/stop/motion procedure, and verifying calibration/teleoperation before collecting demonstrations. M16 software acceptance passed 154 tests and eight actual-browser scenario groups; the accepted version was verified running at 19:59 UTC with its original records, revisions and 50-event sequence preserved. Shared Mac/Notion checkpoints have separately tracked read-back receipts in the continuation report. Keep these software results separate from physical-cycle evidence.

The resumed session delivered complete structured M16 evidence; the Mac independently verified it and confirmed **M16 Done at 20:25:48 UTC**. The user-requested dashboard was opened in the desktop browser. A public provider-check utility is ready on Intel with 18 passing offline checks, but no Intel provider request, calibration, teleoperation or physical acceptance was added. See the continuation report for exact evidence, source provenance and current synchronization receipts.

## Next software gates from the shared Mac — November 14, 2026, 20:49 UTC

The [Mac provider/Gemma handoff, note `91e2e4de`](mac-sync/initial-review/f823677fab02269534cd0173bf6770a4d6bf3e720a6616ba69cde485845f7405.json) reports a new additive transfer package and **42 passing offline Mac tests**, not Linux installation or live provider acceptance. Verify any separately authorized import against its manifest, preserve the existing provider utility and M16 application, and establish private Intel configuration plus bounded real provider evidence before claiming readiness. No package import or configuration restoration was performed in this documentation review.

At the 20:49 UTC handoff, the explicitly invoked **Gemma evidence analyst** in Quality & history was an optional proposal. The owner's approval of it as planned scope was recorded at **21:02:50 UTC**, as described below; implementation remains pending. The named model is `gemma-4-26b-a4b-it`. Its first function would explain saved cycles with exact record/revision references; session comparison would use matched inputs and backend metrics. Implement and evaluate its bounded context, schema/citation checks, stale-revision handling, idempotency, errors, persistence and latency before presenting it as a working feature. Its example response is hand-authored. Gemma does not replace the required Gemini Decision 1 orchestration, Nemotron vision, ElevenLabs finalized speech or local validated execution.

The Mac's actual M01–M16 page audit at **20:36:40–20:36:41 UTC** found only **M03, M04, M06, M15 and M16 Done**. Mentor decisions, speech, evaluation/data, learned skills, a useful detector, the dispatcher, adapters and the physical baseline remain substantive work alongside M08 calibration/teleoperation. Do not describe all work through M16 as complete except robot debugging. The [consolidated status reconciliation](PROJECT_STATUS.md#shared-mac-reconciliation--november-14-2026-2053-utc) records the artifact identity and exact Notion acknowledgments; this review did not independently query Notion or change any task status.

The [subsequently retained M08 confirmation](morph-intel-continuation-20261114T193410Z/Morph-Intel-Handoff-20261114T191514Z/HachingJunction/context/verification/intel-continuation/notion-role-correction-confirmed.json), retrieved on Intel at **20:53:28 UTC**, records the Mac's **20:47:40 UTC** Notion read-back for correction `e907ed5a-48d6-4a6c-a910-b21ffdcd7bf8` and the **20:52:59 UTC** check of current Mac guides. Both use leader `5B91030668` and follower `5AE6075066`; M08 remains In progress. The earlier catalog's lack of a new note did not establish that the separate task update was still pending. Do not retry the resolved correction or infer calibration, teleoperation or physical acceptance from it.

## Approved Gemma planning and implementation gates — November 14, 2026, 21:06 UTC

The [owner-approved plan `028a574e`](mac-sync/snapshots/b3a288f3261f1d2bc52771da067c1965af74b0989e1e1d26367ce4ce0040b739.txt) and [Mac reconciliation `0302c932`](mac-sync/snapshots/2381e586ac85dbfda262dde5b523f5b969cbd143a4f10d6cafd646979e744d04.txt) supersede recommendation-only Gemma wording. Existing **M20** owns G1 Explain this cycle and G2 Compare sessions; **M21** covers failure/stale/duplicate/untrusted-content/replay regressions; **M23** evaluates grounded usefulness, coverage, sample counts and latency; **M24** demonstrates actual useful synthesis with citations while preserving all other sponsor evidence. All four task statuses remain **Waiting** in the Mac's **21:02:42 UTC** read-back; the working plan's final marker was confirmed at **21:04:09 UTC**.

An isolated M20 slice can proceed after M06/M15/M16 and actual Intel Gemma access are verified, using saved M16 simulation. Mark partial implementation scope explicitly when starting work; original full-task dependencies and physical/live acceptance remain intact. The existing 24 task IDs are retained, M16 stays Done, and Gemma alone cannot close M20. Keep backend facts/metrics authoritative and prevent Gemma from dispatching, relabeling reference data or changing outcomes. The received prompt and frozen package were not executed or imported during this review; the earlier 42 Mac offline tests do not establish these Intel implementation gates.

The [additional M08 propagation receipt `f3ab35a1`](mac-sync/snapshots/a96143f9657e9e65a3d8de1931dd39ae533955dec3a14fafb1a076ea5f70b326.txt) confirms checkpoint `e93b8ad0-0709-51eb-8d5a-c592d50e47f0` at **20:58:32 UTC**, with M08 In progress and 0/3 criteria complete. The corrected roles and owner-led diagnostics remain unchanged. This acknowledges documented propagation, not a new physical test, and requires no duplicate task write.


## Incoming work reconciled at 21:12 UTC on November 14, 2026

The second automatic poll succeeded at **21:12:38 UTC**. A separate Intel Gemma implementation session, `f191d039-8f71-48ba-bb6a-91e15bd096c6`, has now started the isolated M20 analyst slice, as reported in [its 21:08:39 UTC start note](mac-sync/snapshots/8fe3f2b879259e3c2644aa4cfe3ffbc3666170b08205166ce693865bfe5f43fb.txt). This supersedes implementation-not-started wording in the earlier dated approval review. Its intended M20 In progress update `b64ac84c-7302-5a48-8549-30ff596a375d` still awaited a separate Notion read-back in the reviewed checkpoint; full task dependencies and M21/M23/M24 acceptance remain unchanged. The incoming note's older stopped-watcher observation is superseded by the verified host process and two successful continuous-mode polls documented in MAC_SYNC.md.

The [21:11:49 UTC package checkpoint](mac-sync/snapshots/a6460bd208ca826b9a7cff27977198e5726e9bd36c62cb065f48ea288fa0bc5d.txt) reports actual Intel verification of the additive archive: 133 listed hashes and 42 offline tests passed; the installer dry-run refused three existing-file conflicts. The current and packaged provider implementation matched byte-for-byte, and the existing Intel README/test adaptations/image fixture were preserved. Credential restoration, real provider checks and working analyst output were still in progress in that checkpoint. These results belong to the separate implementation session; this polling/reconciliation session did not rerun them or modify application code.

The Mac also supplied [a follower motor specification note](mac-sync/snapshots/1fc335569e60699456dbb5fe32c60212e68cd401cc7a3964e6cb90163334a1d7.txt) at **21:10:56 UTC**, distinguishing documented kit variants and recording its M08 source-check update. That is a published-specification report, not an inspection of installed motor labels, adapter output, communication, calibration or teleoperation. Owner-led diagnostics and corrected leader `5B91030668` / follower `5AE6075066` remain unchanged. The [21:07:31 UTC Mac idle receipt](mac-sync/snapshots/ef65a3c030e0629aabb5a291d81ce4b5956d12afcdbbd95b1144a5ab988fe7de.txt) adds no test evidence or new task verification time.

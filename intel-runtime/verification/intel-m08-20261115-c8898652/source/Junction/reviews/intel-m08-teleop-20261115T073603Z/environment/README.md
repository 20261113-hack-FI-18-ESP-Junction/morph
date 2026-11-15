# M08: existing Intel teleoperation environment and command audit

Agent `/root/dashboard`, November 15, 2026 UTC. This audit inspected installed metadata and source, then ran the existing standalone CLI's bounded help path. **The proposed teleoperation command was not executed. No robot was constructed, connected, calibrated or commanded by this audit.** Root owns the operator readiness decision; `/root/shared_sync` is the designated shared reporter.

The owner confirmed the replacement controller as leader **`5B91027633`**. The follower remains **`5AE6075066`**. Earlier leader `5B91030668` is historical. The root's current USB/ownership evidence and the separate [calibration audit](../calibration/) establish the preparation context; environment discovery alone does not establish physical readiness.

## Actual environments

| Purpose | Absolute environment | Python | Installed LeRobot | Other inspected metadata |
| --- | --- | --- | --- | --- |
| Standalone robot workflow; selected for the proposed command | `/home/intel/project-morph/morph-robot/morph-robot-lerobot/.venv` | 3.12.16 | **0.7.0** | draccus 0.11.6, Torch 2.15.0+cpu |
| Existing native Studio backend | `/home/intel/project-morph/morph-ai/morph-physical-ai-studio/application/backend/.venv` | 3.13.18 | **0.6.0** | Studio 0.3.0, physicalai 0.4.1.dev5+g8381d43, draccus 0.10.0, Torch 2.11.0+xpu |

These are measured installed versions, not a claim about the latest public release. The old `/home/intel/physical-ai-studio/application/backend/.venv` path does not exist in this filesystem. The unactivated shell did not resolve `lerobot-teleoperate` on PATH. No installation or Studio change was made.

The standalone project is `/home/intel/project-morph/morph-robot/morph-robot-lerobot`. Its Python executable is `/home/intel/project-morph/morph-robot/morph-robot-lerobot/.venv/bin/python`. Its installed console executable is `/home/intel/project-morph/morph-robot/morph-robot-lerobot/.venv/bin/lerobot-teleoperate`; its absolute shebang selects that environment. The installed `lerobot-0.7.0.dist-info/entry_points.txt` declares `lerobot-teleoperate = lerobot.scripts.lerobot_teleoperate:main`. The actual script is under that environment's `lib/python3.12/site-packages/lerobot/scripts/lerobot_teleoperate.py`.

The absolute executable needs no activation and can be invoked from any directory. For an interactive shell, the equivalent activation command is:

```bash
source /home/intel/project-morph/morph-robot/morph-robot-lerobot/.venv/bin/activate
```

The calibration directories in the proposed command are absolute, so loading them does not depend on the current directory or sourcing a private environment file. Activation changes only the invoking shell; it does not connect hardware.

## Observed help result

Before executing help, this audit read the entrypoint, imports, plugin registration, parser wrapper and SO follower/leader source. The entrypoint imports configuration and implementation modules, but the parser's explicit help branch exits before configuration parsing and the teleoperation function body. No matching third-party `lerobot_robot_*`, `lerobot_camera_*`, `lerobot_teleoperator_*`, `lerobot_policy_*`, `lerobot_env_*` or `lerobot_strategy_*` distribution was installed for automatic plugin discovery.

After root clarified that reviewed imports were allowed while hardware opens/actions remained prohibited, the following existing executable was run from a private temporary directory, with bytecode writes disabled, offline Hugging Face settings and a 45-second bound:

```bash
/home/intel/project-morph/morph-robot/morph-robot-lerobot/.venv/bin/lerobot-teleoperate \
  --robot.type=so101_follower \
  --teleop.type=so101_leader \
  --help
```

It ran from **07:40:43.860181 to 07:40:48.187057 UTC**, exited **0**, and produced **5,210 bytes of stdout and zero stderr bytes**. [Machine receipt](help-result.json); [actual help](teleoperate-help.stdout.txt). Stdout SHA-256: `44ff2dc28a47f631558903791a93d73703a213a44c81ca0abbe7c9faf28a6def`.

Actual help confirms the `so101_follower` / `so101_leader` type selectors, both `.port`, `.id`, `.calibration_dir` and `.use_degrees` options, plus `--teleop_time_s`, `--fps`, `--robot.max_relative_target`, `--robot.disable_torque_on_disconnect`, `--robot.cameras` and `--display_data`. No calibration-bypass option is exposed by this entrypoint. The native Studio environment's teleoperation entrypoint was not run.

## Exact proposed 30-second command — not executed

Root requested preservation of the existing configuration defaults, with no added rate or relative-target clamp. Both existing JSON configurations explicitly use normalized units (`use_degrees: false`), and their IDs and absolute calibration directories are retained below. The default in installed 0.7.0 would otherwise be degrees, so both explicit false values matter.

```bash
/home/intel/project-morph/morph-robot/morph-robot-lerobot/.venv/bin/lerobot-teleoperate \
  --robot.type=so101_follower \
  --robot.port=/dev/serial/by-id/usb-1a86_USB_Single_Serial_5AE6075066-if00 \
  --robot.id=2a1b5cc1-8e89-457e-8828-4d6d065f4ca6 \
  --robot.calibration_dir=/home/intel/project-morph/morph-robot/morph-robot-lerobot/.runtime/lerobot/calibration/robots/so_follower \
  --robot.use_degrees=false \
  --teleop.type=so101_leader \
  --teleop.port=/dev/serial/by-id/usb-1a86_USB_Single_Serial_5B91027633-if00 \
  --teleop.id=13b35ac4-c088-4441-bfc9-c53987742388 \
  --teleop.calibration_dir=/home/intel/project-morph/morph-robot/morph-robot-lerobot/.runtime/lerobot/calibration/teleoperators/so_leader \
  --teleop.use_degrees=false \
  --teleop_time_s=30
```

The [machine-readable proposed command](proposed-command.json) is marked unauthorized for execution by this audit. The exact executable and arguments were checked against the observed help; that is command preparation, not a motor test. The omitted defaults are `fps=60`, `max_relative_target=None`, empty cameras and `display_data=false`. There is no added software motion clamp. Small operator movements, initial pose alignment, the observed wrist/cable arc and no full rotation remain the root's explicit physical readiness conditions.

## Startup, calibration and stopping behavior observed in source

- `teleoperate()` constructs the leader and follower, calls `teleop.connect()` and then `robot.connect()`, and only then enters its `try/finally` around the loop. A connection or calibration failure before the loop is outside that normal cleanup block. Base destructors attempt cleanup, but they are best-effort fallbacks.
- Both SO connect methods default to `calibrate=True`. They open the motor bus and compare calibration; a mismatch or absent calibration can enter the calibration path. When a stored calibration exists, the prompt's ENTER option **writes that calibration to the motors**. It is not a passive acknowledgment. An unexpected calibration prompt must be reviewed before proceeding.
- Leader configuration disables torque and writes motor configuration and operating mode. Follower configuration writes motor configuration, operating mode, PID coefficients and gripper protection/torque settings inside `torque_disabled()`. That context re-enables torque on exit, including an exceptional exit. Startup therefore includes register writes and torque transitions before the timed motion loop.
- The loop reads follower observations, reads the leader's action and writes follower goal positions. `teleop_time_s=30` is checked inside this loop after an iteration. It excludes connection/calibration time and is not a hard deadline if an operation blocks.
- Normal exit or a caught keyboard interrupt reaches sequential `teleop.disconnect()` and `robot.disconnect()`. Leader bus disconnect defaults to disabling torque; follower `disable_torque_on_disconnect` defaults to true. The bus closes its port in a `finally` even if torque disable fails, but a raised leader disconnect can prevent the subsequent follower disconnect call. Torque loss can allow the physical arm to drop; software interruption is not independently verified emergency-stop behavior.
- The earlier 0.6.0-specific diagnostic assumptions must not be silently applied to this 0.7.0 command. The selected installation uses the shared `SOFollower`/`SOLeader` classes and `SerialMotorsBus`; runtime class calibration directory names are `so_follower` and `so_leader`, while CLI type selectors remain `so101_follower` and `so101_leader`.

[Installed metadata and reviewed source hashes](installed-environments.json) records both environments, exact entrypoint metadata, the two existing public configuration hashes and ten inspected standalone source files. [Collection helper](collect_metadata.py) reads only metadata/public source and invokes Python version reporting with `-I -B -S`; it does not import LeRobot or open hardware. The real help check is separately captured above.

The root's latest readiness assessment and the calibration agent's preserved observations remain separate from this software audit. No physical teleoperation acceptance, new calibration, demonstration, stop-method validation or M08 completion is claimed. Shared Mac delivery and Notion readback are owned by the designated reporter and require their own receipts.

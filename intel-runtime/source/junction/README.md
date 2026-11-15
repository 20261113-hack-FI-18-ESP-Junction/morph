# SO-101 robotics workspace

This workspace holds the hardware checks, camera captures, scripts, and project handoff for a LeRobot leader/follower setup using Physical AI Studio.

**All project files and future authored content must be in English.** Everyone working here should read [AGENTS.md](AGENTS.md) first.

- [Project status and handoff](PROJECT_STATUS.md): what works, what was tested, remaining limitations, and the next actions.
- [Periodic Mac context updates](MAC_SYNC.md): five-minute polling, incoming changes, protected document updates, and the review workflow.
- [Robot development gameplan](ROBOT_GAMEPLAN.md): the sequence from hardware verification to demonstrations, training, and evaluation.
- [Camera report and captured outputs](camera-check-2026-11-14/README.md): RGB, depth, infrared, simultaneous previews, and current Studio support.
- [Robot connection map](robot-connections.json): stable controller identities and the last known communication state.
- [Imported Morph project](morph-intel-transfer/morph-context/AGENTS.md): the wider inspection/sorting workflow, architecture, tasks, and team handoff instructions.
- [Active Intel continuation](morph-intel-continuation-20261114T193410Z/Morph-Intel-Handoff-20261114T191514Z/INTEL_CONTINUATION.md): verified new package, dashboard launch, M16 changes, isolated Anomalib environment, and current blockers.

The Studio source is in `/home/intel/physical-ai-studio`; the existing container is `physical-ai-studio-xpu`. The separate Morph dashboard uses port 3001 and its records API uses port 8000. The user corrected the earlier reversed assignment: **leader `5B91030668`**, **follower `5AE6075066`**. The earlier role-based report says the follower works while the user investigates leader communication; its serial association follows this correction, without a new hardware test. Earlier USB and motor failures retain their actual serial numbers and original timestamps. Calibration and teleoperation have no new independent verification. Read [the current connection map](robot-connections.json) and status before operating hardware or interpreting older reports. Keep the imported pairing directory private.

The registered **Morph SO-101 Workstation** is in native Studio on port **3000**. Its robot names/types now match the corrected serial roles, with UUIDs and complete configuration payloads preserved. The separate container Studio on port **7860** had no registered projects at this check. [Role correction and archive notice](morph-intel-continuation-20261114T193410Z/Morph-Intel-Handoff-20261114T191514Z/ROLE_ASSIGNMENT_CORRECTION.md).

A metadata-only inventory can be run from this directory:

```bash
python3 scripts/check_robot_usb.py --container physical-ai-studio-xpu
```

Use each script's `--help` for its interface and read the operating notes before camera or serial-port access. Native capture dependencies are already installed in the Studio container. Use a new output directory for each capture run and preserve the existing reports.

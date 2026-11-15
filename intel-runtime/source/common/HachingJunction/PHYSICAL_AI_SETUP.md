# Physical AI challenge setup

Verified on **November 14, 2026**. This is the software setup record for the [challenge brief](IGNITE_INTEL_PHYSICAL_AI.md). It does not change the competition requirements or resolve the conflicting judging rubrics.

The local machine is an Apple Silicon Mac running macOS. The final robot demonstration is planned for the organizers' Intel Core Ultra Series 3 station. The user is preparing access through NVIDIA Brev; the target has not yet been inspected or installed from this workspace. Brev access alone does not identify which physical machine or accelerators are present.

## Preferred workflow: Mac as the client

The user clarified that all final execution should run on the Intel station. **The Mac only needs the Brev CLI, SSH, and a browser.** Full local Studio, Anomalib, OpenVINO, and FFmpeg installations are optional development tools, not prerequisites for remote operation. Use the Intel installation section below once access is ready.

The optional Mac environments were already installed during preparation. They occupy about **3.5 GB combined**; caches and the previously prepared tools bring `.junction-setup` to about **11 GB total**, with approximately **64 GiB free on disk** at the final check. No Studio server was started, and all known installation/model-test sessions have ended. Installed packages consume disk space but do not keep a model running.

## Authorized local application development

The owner subsequently authorized M06 backend development on this Mac while preparing the Intel station separately. The application now lives in [station/](station/README.md), using the existing general FastAPI/Pydantic environment and SQLite. Its software/API verification is in [station/VERIFICATION.md](station/VERIFICATION.md). This does not change the intended final Intel execution or the separate Studio/Anomalib environments.

## Verification record

| Check | Observed result on November 14, 2026 |
| --- | --- |
| Mac Anomalib 2.7.0 dependencies | 88 packages installed; dependency check passed |
| Mac Studio 0.3.0 dependencies | 219 packages installed; dependency check, CLI help, Torch tensor operation, and OpenCV import passed |
| Synthetic Anomalib fit and Torch inference | Passed using generated images and random backbone weights |
| Anomalib OpenVINO export | XML and BIN generated |
| Mac OpenVINO execution | Failed with Xbyak internal error in the sandbox; cause unconfirmed. Elevated retries were cancelled before any confirmed execution. No Torch/OpenVINO parity result. |
| FFmpeg | FFmpeg 8.1.3 installed; scripts select its keg. A separate FFmpeg 9 installation is also present from the initial Homebrew command. |
| Studio web UI, video decoding, policy run | Not tested; local validation stopped after the client-only clarification |
| Intel package profiles | Linux dependency resolution and installation dry-runs passed; actual installation/runtime checks pending remote access |
| Robot, cameras, calibration, full physical cycle | Not tested |

The synthetic report is `.junction-setup/smoke/anomalib/20261114T122227Z-8b9a93aa/report.json`. Preserve its failed overall status alongside the successful intermediate checks.

Homebrew also installed native dependencies. Its `ca-certificates` post-install refresh stalled and was interrupted; the prior certificate bundle remained intact and readable, and HTTPS requests to PyPI and GitHub still passed. The certificate refresh was not rerun after the user stopped further local setup. This is a local package-maintenance follow-up, unrelated to target hardware verification.

## Software profiles

Keep the environments separate. Studio and Anomalib have different PyTorch, OpenVINO, and `jsonargparse` requirements. Installing everything into one environment is not the supported project setup.

| Component | Local development profile | Intel target profile |
| --- | --- | --- |
| Python | 3.12.13 | Managed Python 3.12, isolated from Ubuntu's system Python |
| Physical AI Studio | 0.3.0, CPU extra | 0.3.0, Intel XPU extra |
| Physical AI Runtime / training library | `physicalai==0.3.0`, `physicalai-train==0.3.0` | Same coordinated versions |
| Studio PyTorch | 2.11.0 | 2.11.0 with the official XPU wheels |
| Studio OpenVINO | 2026.4.1 | 2026.4.1 |
| Anomalib | **2.7.0**, image training and OpenVINO export dependencies | **2.7.0**, same core model/export versions |
| Anomalib PyTorch / torchvision | 2.14.0 / 0.29.0 | 2.14.0 / 0.29.0 with the official CPU wheels |
| Anomalib OpenVINO / NNCF | 2026.3.1 / 3.3.0 | Same versions, then validate target CPU/GPU/NPU |
| Native video libraries | FFmpeg **8**, including shared libraries for TorchCodec | Ubuntu FFmpeg and native OpenCV/USB libraries |

Studio 0.3.0 is the current public Studio release found during this setup; it is a **project choice pending the event starter/version confirmation**, not a newly established competition requirement. Anomalib 2.7.0 is the user's requested version and appears on the equipment slide.

Exact platform-specific dependency sets are stored in `setup/*.lock`; the corresponding `.in` files record the direct dependencies. The local Mac profiles have been installed. The Intel profiles have passed dependency resolution and installation dry-runs, but have not been installed on the target.

The Studio distribution includes its browser UI, SO-101 support, robot communication dependencies, camera support, and the training library. Do not install a separate latest LeRobot package into this environment: use the versions resolved with Studio. Anomalib's profile includes ONNX/ONNXScript export and OpenVINO inference. The prepared general environment in `.junction-setup/python` remains available for FastAPI, dashboard work, and the Modal CLI.

## Optional local development on this Mac

These commands are not needed for the preferred remote workflow. If local development is desired later, run from the `HachingJunction` workspace:

```bash
# Start the installed Studio UI. Stop it with Ctrl-C in that terminal.
bash setup/run-studio.sh
```

Open `http://127.0.0.1:7860`. The launcher binds to loopback and stores Studio data and settings under `.junction-setup/physicalai-storage`. Starting the server does not start a teleoperation or policy run. Hardware calibration and control remain intentional actions in Studio.

For Anomalib development:

```bash
source setup/activate-anomalib.sh
python setup/smoke-anomalib.py
```

The smoke test creates generated images and a PatchCore model with **random backbone weights**, runs a small fit, exports XML/BIN, and compares PyTorch and OpenVINO CPU anomaly scores. It downloads no training data or pretrained model. Results are saved under `.junction-setup/smoke/anomalib/<run-id>/report.json`. This verifies an installation path; it is **not a useful brick detector, quality measurement, hardware benchmark, or robot test**.

To reproduce the Mac environments after copying this workspace:

```bash
# Native prerequisite; TorchCodec 0.11.1 needs FFmpeg 4–8 shared libraries.
brew install ffmpeg@8
bash setup/setup-physicalai-macos.sh
bash setup/setup-anomalib-macos.sh
```

The launch/setup scripts select the FFmpeg 8 keg on Apple Silicon. A static `imageio-ffmpeg` executable alone does not supply the required shared libraries. The Mac setup scripts use the existing `uv` and Python 3.12, downloading a managed interpreter into the workspace if necessary.

## Install on the Intel station

Transfer the project documentation and `setup/` sources to the station. Do not copy Mac virtual environments, credentials, or package caches to Linux. For a Brev-managed session, keep project files in its persistent workspace and confirm that the SSH target is the actual organizer machine with the connected robot/cameras.

On the station, from the copied project directory:

```bash
# Inventory only; exits before installation if this is not the target platform.
bash setup/setup-intel.sh --preflight

# Installs native prerequisites through apt, then two isolated Python profiles.
bash setup/setup-intel.sh --install-system-packages

# When native prerequisites already exist, omit the apt step:
# bash setup/setup-intel.sh

# Intentionally start the Studio server after installation.
bash setup/run-studio.sh
```

The installer expects Ubuntu x86_64 on an Intel Core Ultra CPU. It preserves Ubuntu's system Python, uses Python 3.12 for both profiles, and saves separate runtime reports to `.junction-setup/checks/`. It tests a tiny synthetic OpenVINO operation on the CPU, GPU, and NPU. Missing devices and failed compilations are reported as unavailable/failed; they are not silently replaced with CPU results. Passing this test does not prove that a chosen VLA or anomaly model supports that device.

The installer does not install or replace the preinstalled Intel GPU/NPU drivers, alter device groups, calibrate the robot, open cameras/serial ports, or start training. If device access is missing, use the report with the station mentor to confirm the supported driver and permissions configuration. The bootstrap may return failure after packages install if accelerator validation fails; the environments and diagnostics are retained for repair.

For an SSH connection configured by Brev, forward the loopback UI from the Mac using the actual machine alias:

```bash
brev login
brev refresh
brev ls
ssh -N -L 7860:127.0.0.1:7860 YOUR_MACHINE_ALIAS
```

Use the browser login flow and existing SSH configuration. Do not place passwords, tokens, or private keys in this project. `YOUR_MACHINE_ALIAS` is a placeholder, not an installed host. If local Studio is already using port 7860, use `7861:127.0.0.1:7860` and open the local port 7861 instead. No cloud instance is provisioned by these commands or setup scripts.

## What remains before the challenge workflow is ready

1. **Verify the station.** Confirm the assigned Intel model/OS, CPU/GPU/NPU runtime checks, robot power/stop instructions, leader/follower identities, and the real camera devices. Do not infer camera capture or calibration from a device listing.
2. **Set up the physical environment in Studio.** Identify the wrist, overhead, and inspection cameras; verify live images and frame timestamps; follow the supplied SO-101 calibration and workspace limits. A first permitted movement needs direct observation and the specified stop procedure.
3. **Connect training access.** The equipment slide names Modal. Current Studio documentation describes remote trainers and SSH-managed training; it does not establish a turnkey Modal integration. Confirm the organizer's starter/trainer URL, GPU allocation, access, and export procedure. Configure Hugging Face access through Studio **Settings → General → Hugging Face** for policies that need it. The native Studio backend does not use an arbitrary `.env` `HF_TOKEN` as its settings source.
4. **Collect the actual data.** Record leader-arm demonstrations for grasp, presentation, and correct-bin placement. Capture representative good/defective brick images under the inspection camera; keep training, threshold tuning, and independent reference-labeled validation examples distinct. Save original frames, object IDs, and unambiguous timestamps.
5. **Train and connect the models.** Train the required policy workflow and an actual Anomalib detector, select a data-based anomaly threshold, and connect the structured inspection result to the intended robot action. The setup scripts do not implement this integration or invent its API.
6. **Verify the physical cycle and optimization.** Run observed good and defective cycles, record commanded/observed destinations and confirmation evidence, and measure inference, movement, verification, and full-cycle times separately. Benchmark supported exported models on the target GPU/NPU, checking quality alongside latency. Preserve failed, aborted, and unverified results and retries under the definitions in [AGENTS.md](AGENTS.md).

No additional database or container service is needed for this software setup. The application dashboard and persisted session/cycle/attempt/outcome records are later implementation work; the installed packages do not provide project-specific integration automatically.

## Sources checked on November 14, 2026

- [Physical AI Studio app/v0.3.0 release](https://github.com/open-edge-platform/physical-ai-studio/releases/tag/app%2Fv0.3.0): coordinated versions, installation extras, and supported Python versions.
- [Studio installation guide at app/v0.3.0](https://github.com/open-edge-platform/physical-ai-studio/blob/app/v0.3.0/application/docs/01-installation.md): native prerequisites and deployment choices.
- [Studio backend metadata at app/v0.3.0](https://github.com/open-edge-platform/physical-ai-studio/blob/app/v0.3.0/application/backend/pyproject.toml): exact constraints used for the separate Studio profile.
- [Anomalib 2.7.0 on PyPI](https://pypi.org/project/anomalib/2.7.0/) and [release lock file](https://github.com/open-edge-platform/anomalib/blob/lib/v2.7.0/uv.lock): exact requested version, dependency extras, and core baseline versions.
- [TorchCodec 0.11.1](https://github.com/pytorch/torchcodec/tree/v0.11.1): FFmpeg shared-library requirements.
- [NVIDIA Brev connectivity](https://docs.nvidia.com/brev/cli/connectivity): machine aliases and SSH port forwarding. The installed local CLI was present but logged out when checked.

The event-specific hardware, training-provider, and challenge requirements remain sourced to the reviewed portal/photos in the [working brief](IGNITE_INTEL_PHYSICAL_AI.md). They were not newly established by the package documentation.

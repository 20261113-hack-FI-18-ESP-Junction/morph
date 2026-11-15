# Camera checks — November 14, 2026

The connections to the RealSense D415 and webcam work. The D415 already outputs computed depth; we do not need our own algorithm to calculate depth from stereo images. The script `../scripts/check_realsense_depth.py` captured, checked, and saved actual depth data. The robot arms were not calibrated during these checks.

## What the RealSense D415 returns

The native check through `pyrealsense2` enabled four streams simultaneously:

| Stream | Format | Tested configuration | Measured result |
| --- | --- | --- | --- |
| Color image | RGB8 | 640 × 480, 30 FPS | 149 unique frames, 29.76 FPS |
| Depth image | Z16, 16-bit values | 640 × 480, 30 FPS | 149 unique frames, 29.76 FPS |
| Left infrared image | Y8 | 640 × 480, 30 FPS | 149 unique frames, 29.76 FPS |
| Right infrared image | Y8 | 640 × 480, 30 FPS | 149 unique frames, 29.76 FPS |

After warming up with 30 unique depth frames, the measurement lasted 5.0065 seconds. No stream had frame-number gaps, repeated frames, or missing parts of a frameset; there were no timeouts. On average, 89.56% of depth-image pixels had nonzero depth. This measures coverage of this scene, not measurement accuracy or long-term stability.

The unit scale returned by the SDK was `0.0010000000474974513` meters per unit. The conversion is `depth_m = Z16 * depth_units_m`. In the saved frame, the value at image coordinate `(x=320, y=240)` is 734, corresponding to approximately 0.734 m of depth in the depth camera's coordinate system. A value of 0 indicates an invalid or missing measurement. Always read the scale from the SDK; do not assume it is the same for every device or configuration.

- [Overview of all four streams](realsense-overview.png).
- [Color image](realsense-depth/color.jpg).
- [Depth visualization](realsense-depth/depth_visualization_not_metric.png): a 0–2 m scale, with black indicating a missing measurement. This color image is for display; do not calculate metric depth from it.
- [Original Z16 depth in a 16-bit PNG file](realsense-depth/depth_raw16.png): numerical values are preserved for further calculations.
- [Left IR](realsense-depth/left_ir.png) and [right IR](realsense-depth/right_ir.png).
- [Full native check report](realsense-depth/report.json).

These saved streams are not geometrically aligned to RGB. To obtain the depth of a pixel in the color image, use the SDK's alignment functionality. Calculating a 3D point also requires the camera intrinsics; expressing that point in the robot arm's coordinate system additionally requires the transformation between the camera and robot.

## What Studio currently uses

The actual installed versions of the application and library were inspected. The native RealSense driver opens RGB and Z16 depth and provides `read_depth()` and `read_rgbd()`. Its `read()` and `read_latest()` methods return only RGB. The depth methods return raw Z16 values without converting them to meters.

Studio currently uses RGB in its shared preview and demonstration recording. `application/backend/src/internal_datasets/lerobot/video_encoding_settings.py:195` contains `_UnsupportedDepthEncoderConfig`, which raises `Depth video recording is not supported by Studio` when used. Selecting `output_type=depth` or `both` alone is insufficient: that field is not currently passed to the driver.

We already have a working diagnostic script for obtaining depth images. Adding depth preview and metric depth storage to Studio requires support in its capture path and recorder. This was not implemented as part of these checks.

Inspected paths in the local project at `/home/intel/physical-ai-studio`:

- `application/backend/src/api/camera.py:140`: JPEG preview from `read_latest()`.
- `application/backend/src/workers/camera_worker.py:103`: image in the recording path.
- `application/backend/src/runtime_session/store.py:43`: three-channel image; `uint8` at line 139.
- `application/backend/src/internal_datasets/lerobot/video_encoding_settings.py:195`: depth recording is unsupported.
- `application/backend/src/utils/camera_factory.py:44`: forwarding of width, height, and FPS settings.

Inspected paths inside the container under `/app/application/backend/.venv/lib/python3.13/site-packages/`:

- `physicalai/capture/cameras/realsense/_camera.py:73`: RGB + Z16; `read_depth()` at line 216 and `read_rgbd()` at line 249.
- `physicalai/capture/transport/_publisher_worker.py:189`: the publisher reads the ordinary RGB stream.

## Individual and simultaneous previews

Three physical external cameras were detected. The duplicate RealSense UVC entry was excluded in favor of the native driver. Internal IPU7 nodes were not counted as external cameras.

| Camera | Individual FPS | Simultaneous FPS | Assessment of the saved image |
| --- | --- | --- | --- |
| RealSense D415 | 29.60 | 29.40 | Clear image of the work surface |
| Webcam Audio: Webcam | 29.79 | 29.82 | Clear image; check placement and occlusion for the task |
| USB2.0_CAM1 | 29.00 | 29.20 | Image is severely out of focus; transmission works |

All configurations use 640 × 480 at a requested 30 FPS. FPS in this table measures JPEG preview delivery through Studio, not the sensor directly. The simultaneous measurement had 4.952 seconds of shared overlap. See the [simultaneous image overview](camera-overview.png) and [successful simultaneous check report](studio-concurrent/report.json).

The first attempt to switch quickly from individual to simultaneous previews returned `CaptureTimeoutError: no publisher responded within timeout` for RealSense. The log showed the old publisher starting to shut down, followed by a new connection 457 ms later. We suspect an overlap between reopening the camera and shutting down the old process; this is not a confirmed cause. After the previous streams had fully stopped, starting all three simultaneously with no startup delay succeeded. The original failure is preserved in the [initial report](studio-initial/report.json). The diagnostic script now waits 10 seconds after closing by default; this does not constitute an application bug fix.

For the additional USB2.0_CAM1, we only read support for standard V4L2 focus controls. `focus_absolute`, `focus_auto`, and `focus_relative` are unsupported. See the [report](focus-controls.json). This does not establish whether the lens is manually adjustable or fixed; no focus settings were changed.

## Reproduction and device identity

The capture scripts are `../scripts/check_cameras.py` and `../scripts/check_realsense_depth.py`. They use the dependencies already installed in the container. Before running the native RealSense check directly, close Studio previews and wait for their captures to release the device. Both scripts require a new output directory and do not overwrite previous results.

The overview images can be regenerated offline from the original saved frames and reports with Pillow. From this directory, run:

```bash
python3 ../scripts/render_camera_overviews.py --input-dir . --cam1-note "Out of focus in this saved frame"
```

This overwrites only `camera-overview.png` and `realsense-overview.png`. It does not open cameras or modify the original sensor images. English labels and measured FPS values are rendered into the overviews; the optional note records the visual assessment of this particular USB2.0_CAM1 frame.

For RealSense, use **SDK serial number `243622061552`**. The USB inventory for the same connected device shows a different identifier, `344223023467`; that is not the serial number to pass to `config.enable_device()`. Ordinary `/dev/video*` numbers are not treated as persistent identifiers. The tested Studio settings are saved in `camera-configs.json`; saving them did not create project cameras or demonstrations in the application.

After the checks, connections were closed, the native `pipeline.stop()` succeeded, and the container process list no longer contained camera publishers. The application's `/api/health` returned `healthy`. No additional motor tests, movements, or calibration were performed.

The [verified official RealSense sources](reference-notes.md) explain onboard depth computation, Z16 conversion, invalid values, image alignment, and coordinate systems.

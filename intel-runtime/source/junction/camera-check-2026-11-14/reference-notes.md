# Official references for the RealSense D415 depth camera

Verification date: **2026-11-14**.

The sources below were retrieved directly over HTTPS with `urllib` or `curl` and read. Findings are paraphrased; this document does not use verbatim quotations or unverified web citation identifiers. No cameras were opened while preparing these notes.

**Onboard depth computation**

```text
https://dev.realsenseai.com/docs/depth-post-processing/
https://www.realsenseai.com/depth-camera-d415/
```

The official depth post-processing article explains that D4xx cameras compute depth on the onboard D4 ASIC. The D415 product page confirms that it uses the Vision Processor D4. Receiving a depth stream therefore does not require our own algorithm to calculate depth from the two infrared images. Any filtering or other post-processing of the depth stream is a separate task.

**Z16 format, units, and invalid measurements**

```text
https://raw.githubusercontent.com/wiki/realsenseai/librealsense/Projection-in-RealSense-SDK-2.0.md
```

The depth formats section describes Z16 as one unsigned 16-bit value per pixel. Convert the value to meters with `depth_m = raw_z16 * depth_scale`; obtain the scale from the SDK, for example through `get_depth_scale()`. Do not assume the scale based on the file format alone. A zero value means that depth could not be determined for that pixel, so exclude it from distance measurements.

**Image alignment and 3D coordinates**

```text
https://raw.githubusercontent.com/wiki/realsenseai/librealsense/Projection-in-RealSense-SDK-2.0.md
https://raw.githubusercontent.com/realsenseai/librealsense/master/wrappers/python/examples/align-depth2color.py
```

Individual streams have their own image and spatial coordinate systems. SDK alignment maps between depth and color images; the official Python example uses `rs.align(rs.stream.color)` followed by `align.process(frames)`. Equal image resolutions alone do not mean that corresponding pixels already represent the same points in the scene.

Deprojection with `rs2_deproject_pixel_to_point` converts an image coordinate, depth in meters, and the relevant camera intrinsics into a 3D point in that stream's coordinate system. The documentation defines its axes as x to the right, y downward, and z forward from the camera.

**Implication for the robotics project**

The following is an inference for our integration, not an additional camera capability claimed by the sources above: using a detected 3D point to move the arm requires knowing or calibrating the transformation between the camera and the robot's coordinate system. RGB/depth alignment does not determine this external relationship.

Successful Z16 capture and the proportion of nonzero values confirm data acquisition and measurement coverage. By themselves, they do not establish geometric depth accuracy or completed camera-to-robot calibration.

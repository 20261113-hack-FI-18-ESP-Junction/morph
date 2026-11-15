#!/usr/bin/env python3
"""Render English camera overviews from saved frames and JSON reports with Pillow."""

import argparse
from datetime import datetime
import json
from pathlib import Path


BACKGROUND = "#131b24"
FOREGROUND = "#f2f5f8"
MUTED = "#b5c1cc"
WIDTH = 1340
MARGIN = 20


def read_json(path):
    return json.loads(path.read_text(encoding="utf-8"))


def draw_label(canvas, text, x, y, width, size=22, *, bold=False, color=FOREGROUND):
    """Fit each label to its allocated width and reject unexpected overflow."""
    from PIL import ImageDraw, ImageFont

    draw = ImageDraw.Draw(canvas)
    filename = "DejaVuSans-Bold.ttf" if bold else "DejaVuSans.ttf"
    font_path = Path("/usr/share/fonts/truetype/dejavu") / filename
    font_source = str(font_path) if font_path.exists() else filename
    for font_size in range(size, 13, -1):
        font = ImageFont.truetype(font_source, font_size)
        bounds = draw.textbbox((x, y), text, font=font, anchor="lt")
        if bounds[2] <= x + width and bounds[3] <= canvas.height - MARGIN:
            draw.text((x, y), text, font=font, fill=color, anchor="lt")
            return
    raise ValueError(f"Label does not fit: {text!r}")


def paste_frame(canvas, source, x, y, width, height):
    """Preserve image aspect ratio and contrast; never save to the source path."""
    from PIL import Image, ImageOps

    with Image.open(source) as frame:
        source_size = frame.size
        preview = ImageOps.contain(frame.convert("RGB"), (width, height))
        canvas.paste(preview, (x + (width - preview.width) // 2,
                               y + (height - preview.height) // 2))
    return source_size


def english_date(timestamp):
    date = datetime.fromisoformat(timestamp.replace("Z", "+00:00")).date()
    months = ("January February March April May June July August September "
              "October November December").split()
    return f"{months[date.month - 1]} {date.day}, {date.year}"


def render_previews(root, report, date_label, cam1_note):
    from PIL import Image

    records = report["concurrent"]
    selectors = (
        ("RealSense D415", lambda camera: camera["driver"] == "realsense"),
        ("Webcam", lambda camera: camera["name"] == "Webcam Audio: Webcam"),
        ("USB2.0_CAM1", lambda camera: camera["name"].startswith("USB2.0_CAM1")),
    )
    canvas = Image.new("RGB", (WIDTH, 540), BACKGROUND)
    draw_label(canvas, f"Simultaneous Studio previews · {date_label}",
               MARGIN, 22, WIDTH - 2 * MARGIN, 28, bold=True)
    for index, (label, matches) in enumerate(selectors):
        found = [record for record in records if matches(record["camera"])]
        if len(found) != 1 or not found[0]["ok"]:
            raise ValueError(f"Expected exactly one successful capture for {label}")
        record = found[0]
        x = MARGIN + index * 440
        frame_name = record["frame_file"]
        if Path(frame_name).name != frame_name:
            raise ValueError("Expected a frame filename within studio-concurrent")
        width, height = paste_frame(canvas, root / "studio-concurrent" / frame_name,
                                    x, 78, 420, 315)
        draw_label(canvas, label, x, 411, 420, 22, bold=True)
        draw_label(canvas, f"{width} × {height} · {record['preview_fps']:.2f} FPS",
                   x, 445, 420, 18, color=MUTED)
        if label == "USB2.0_CAM1" and cam1_note:
            draw_label(canvas, cam1_note, x, 474, 420, 17, color=MUTED)
    overlap = report["concurrent_overlap_seconds"]
    draw_label(canvas, f"JPEG preview delivery FPS · All three streams overlapped for {overlap:.3f} s.",
               MARGIN, 503, WIDTH - 2 * MARGIN, 16, color=MUTED)
    return canvas


def render_realsense(root, report, date_label):
    from PIL import Image

    if report["status"] != "completed":
        raise ValueError("The native RealSense check did not complete")
    canvas = Image.new("RGB", (WIDTH, 1242), BACKGROUND)
    draw_label(canvas, f"RealSense D415: four verified streams · {date_label}",
               MARGIN, 22, WIDTH - 2 * MARGIN, 28, bold=True)
    panels = (
        ("color.jpg", "RGB color image", "color"),
        ("depth_visualization_not_metric.png", "Z16 depth visualization", "depth"),
        ("left_ir.png", "Left infrared image", "left_ir"),
        ("right_ir.png", "Right infrared image", "right_ir"),
    )
    for index, (filename, label, stream) in enumerate(panels):
        x = MARGIN + (index % 2) * 660
        y = 78 + (index // 2) * 550
        width, height = paste_frame(canvas, root / "realsense-depth" / filename,
                                    x, y, 640, 480)
        draw_label(canvas, label, x, y + 496, 640, 22, bold=True)
        if stream == "color":
            fps = report["streams"][stream]["observed_unique_fps"]
            detail = f"{width} × {height} · {fps:.2f} FPS"
        elif stream == "depth":
            detail = "0–2 m display only · black = invalid measurement"
        else:
            detail = "Y8 · original contrast"
        draw_label(canvas, detail, x, y + 526, 640, 18, color=MUTED)
    draw_label(canvas, "Depth camera coordinates. RGB and depth are not aligned in these images.",
               MARGIN, 1205, WIDTH - 2 * MARGIN, 18, color=MUTED)
    return canvas


def main():
    parser = argparse.ArgumentParser(
        description="Regenerate two English overview PNGs from saved camera checks. "
                    "Requires Pillow and DejaVu Sans; performs no camera I/O.",
        epilog="Reads studio-concurrent/ and realsense-depth/ under the input directory. "
               "Overwrites only camera-overview.png and realsense-overview.png there; "
               "original sensor images and reports remain unchanged.",
    )
    parser.add_argument("--input-dir", required=True, type=Path,
                        help="Directory containing the saved camera check results")
    parser.add_argument("--cam1-note", default="",
                        help="Optional English visual assessment of the saved USB2.0_CAM1 frame")
    args = parser.parse_args()
    root = args.input_dir.resolve(strict=True)
    preview_report = read_json(root / "studio-concurrent/report.json")
    depth_report = read_json(root / "realsense-depth/report.json")
    date_label = english_date(preview_report["timestamp_utc"])
    # Build both complete images before replacing either derived overview.
    outputs = {
        "camera-overview.png": render_previews(root, preview_report, date_label, args.cam1_note),
        "realsense-overview.png": render_realsense(root, depth_report, date_label),
    }
    for filename, canvas in outputs.items():
        destination = root / filename
        canvas.save(destination)
        print(f"Saved {destination} ({canvas.width} × {canvas.height})")


if __name__ == "__main__":
    main()

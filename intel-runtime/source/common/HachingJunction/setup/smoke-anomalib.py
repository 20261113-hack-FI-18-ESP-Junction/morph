#!/usr/bin/env python3
"""Exercise Anomalib training, OpenVINO export and inference on synthetic images.

This is an installation test, not a brick detector or hardware benchmark. It uses
random backbone weights and generated images, downloads no model or dataset, and
does not connect to a camera or robot. Every run keeps its own evidence directory.
"""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
from importlib.metadata import version
import json
import os
from pathlib import Path
import platform
import sys
import time
import traceback
from uuid import uuid4


def run(output_root: Path) -> tuple[Path, bool]:
    run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ") + "-" + uuid4().hex[:8]
    run_dir = output_root.resolve() / run_id
    run_dir.mkdir(parents=True, exist_ok=False)
    report: dict = {
        "run_id": run_id,
        "started_at": datetime.now(timezone.utc).isoformat(),
        "data_mode": "synthetic",
        "purpose": "installation smoke test; no detection-quality or physical-hardware claim",
        "backbone_pretrained": False,
        "robot_connected": False,
        "platform": platform.platform(),
        "machine": platform.machine(),
        "python": sys.version,
        "checks": {},
        "status": "in_progress",
    }
    # Confine third-party caches and generated output to this test's directory.
    os.environ.setdefault("MPLCONFIGDIR", str(output_root.resolve() / "cache" / "matplotlib"))
    os.environ.setdefault("TORCH_HOME", str(run_dir / "torch-cache"))
    os.environ.setdefault("HF_HOME", str(run_dir / "hf-cache"))
    os.environ.setdefault("HF_HUB_OFFLINE", "1")
    previous_dir = Path.cwd()
    os.chdir(run_dir)
    started = time.monotonic()
    try:
        print("Loading Anomalib and OpenVINO for a synthetic installation test...", flush=True)
        import numpy as np
        import openvino as ov
        from PIL import Image
        import torch
        from anomalib.data import Folder
        from anomalib.deploy import OpenVINOInferencer
        from anomalib.engine import Engine
        from anomalib.models import Patchcore

        packages = ("anomalib", "torch", "torchvision", "lightning", "openvino", "nncf", "onnx", "onnxscript")
        report["versions"] = {name: version(name) for name in packages}
        assert report["versions"]["anomalib"] == "2.7.0", "This test targets exactly Anomalib 2.7.0."
        report["openvino_available_devices"] = ov.Core().available_devices
        report["checks"]["imports"] = "passed"
        torch.manual_seed(42)
        torch.set_num_threads(2)
        rng = np.random.default_rng(42)
        samples: list[Path] = []
        for subdir, count, defective in (
            ("train/good", 8, False),
            ("test/good", 4, False),
            ("test/defect", 4, True),
        ):
            image_dir = run_dir / "dataset" / subdir
            image_dir.mkdir(parents=True)
            for index in range(count):
                pixels = np.clip(rng.normal(110, 8, (64, 64, 3)), 0, 255).astype(np.uint8)
                pixels[16:48, 16:48, 0] = 190
                if defective:
                    pixels[24:40, 24:40] = (10, 10, 10)
                image_path = image_dir / f"synthetic-{index:02}.png"
                Image.fromarray(pixels).save(image_path)
                if subdir.startswith("test/") and index == 0:
                    samples.append(image_path)

        datamodule = Folder(
            name="synthetic_installation_check",
            root=run_dir / "dataset",
            normal_dir="train/good",
            normal_test_dir="test/good",
            abnormal_dir="test/defect",
            train_batch_size=4,
            eval_batch_size=2,
            num_workers=0,
            seed=42,
        )
        model = Patchcore(
            backbone="resnet18",
            layers=("layer2", "layer3"),
            pre_trained=False,
            coreset_sampling_ratio=0.1,
            num_neighbors=3,
            pre_processor=Patchcore.configure_pre_processor(image_size=(64, 64)),
            evaluator=False,
            visualizer=False,
        )
        engine = Engine(
            accelerator="cpu",
            devices=1,
            max_epochs=1,
            logger=False,
            enable_progress_bar=False,
            enable_model_summary=False,
            default_root_dir=run_dir / "training",
        )
        print("Fitting PatchCore on 8 generated training images...", flush=True)
        engine.fit(model=model, datamodule=datamodule)
        model.eval()
        report["checks"]["synthetic_training"] = "passed"
        report["memory_bank_shape"] = list(model.model.memory_bank.shape)

        torch_scores: list[float] = []
        for sample in samples:
            array = np.asarray(Image.open(sample).convert("RGB"), dtype=np.float32) / 255.0
            tensor = torch.from_numpy(array).permute(2, 0, 1).unsqueeze(0)
            with torch.inference_mode():
                score = model(tensor).pred_score
            assert score is not None and torch.isfinite(score).all(), "Torch returned an invalid anomaly score."
            torch_scores.append(float(score.flatten()[0]))
        report["checks"]["torch_inference"] = "passed"

        print("Exporting the synthetic test model to OpenVINO...", flush=True)
        xml_path = model.to_openvino(
            export_root=run_dir / "exports",
            model_file_name="synthetic_patchcore",
            input_size=(64, 64),
            onnx_kwargs={"opset_version": 18},
        )
        assert xml_path.exists() and xml_path.with_suffix(".bin").exists(), "OpenVINO model files are missing."
        report["exported_model"] = str(xml_path)
        report["checks"]["openvino_export"] = "passed"

        print("Comparing Torch and OpenVINO CPU anomaly scores...", flush=True)
        inferencer = OpenVINOInferencer(path=xml_path, device="CPU", config={"INFERENCE_PRECISION_HINT": "f32"})
        openvino_scores: list[float] = []
        for sample in samples:
            prediction = inferencer.predict(sample)
            assert prediction.pred_score is not None and np.isfinite(prediction.pred_score).all(), "OpenVINO returned an invalid anomaly score."
            openvino_scores.append(float(np.asarray(prediction.pred_score).reshape(-1)[0]))
        report["checks"]["openvino_cpu_inference"] = "passed"
        report["torch_scores"] = torch_scores
        report["openvino_scores"] = openvino_scores
        report["score_comparison"] = {"rtol": 0.01, "atol": 0.001, "count": len(samples)}
        np.testing.assert_allclose(openvino_scores, torch_scores, rtol=0.01, atol=0.001)
        report["checks"]["torch_openvino_score_agreement"] = "passed"
        report["status"] = "passed"
    except Exception as error:
        report["status"] = "failed"
        report["error"] = f"{type(error).__name__}: {error}"
        report["traceback"] = traceback.format_exc()
        traceback.print_exc()
    finally:
        os.chdir(previous_dir)
        report["finished_at"] = datetime.now(timezone.utc).isoformat()
        report["elapsed_seconds"] = round(time.monotonic() - started, 3)
        report_path = run_dir / "report.json"
        report_path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
        print(f"Synthetic installation test: {report['status']}")
        print(f"Report: {report_path}")
    return report_path, report["status"] == "passed"


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output-root",
        type=Path,
        default=Path(__file__).resolve().parents[1] / ".junction-setup" / "smoke" / "anomalib",
    )
    arguments = parser.parse_args()
    _, passed = run(arguments.output_root)
    raise SystemExit(0 if passed else 1)

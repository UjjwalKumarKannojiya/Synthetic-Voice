"""Read-only validation/test screen for applying the ASVspoof model to live windows."""

from __future__ import annotations

import argparse
import csv
import json
import random
import sys
from pathlib import Path
from typing import Any

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.core.asvspoof_detector import ASVspoofDetector
from app.core.audio_utils import decode_audio_file
from app.core.detector import Detector, DetectorConfig
from app.core.streaming import StreamSession
from src.svf.eval.metrics import classification_metrics, threshold_at_eer


class ASVspoofWindowAdapter:
    """Expose the complete-clip ASVspoof model as a 2-second stream scorer."""

    def __init__(self, model: ASVspoofDetector) -> None:
        self.model = model
        self.sample_rate = model.sample_rate
        self.window_seconds = 2.0
        self.window_samples = round(self.window_seconds * self.sample_rate)
        self.hop_samples = self.sample_rate
        self.threshold = model.threshold
        self.config = DetectorConfig(
            hop_seconds=1.0,
            uncertain_band=0.05,
            threshold=self.threshold,
        )

    def predict_window(self, audio: np.ndarray, sample_rate: int) -> float:
        return self.model.predict_clip(audio, sample_rate)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--validation-manifest",
        type=Path,
        default=ROOT / "data" / "manifests" / "asvspoof_la_val.csv",
    )
    parser.add_argument(
        "--test-manifest",
        type=Path,
        default=ROOT / "data" / "manifests" / "asvspoof_la_test.csv",
    )
    parser.add_argument("--per-class", type=int, default=250)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--frame-samples", type=int, default=4096)
    return parser.parse_args()


def select_rows(manifest: Path, per_class: int, seed: int) -> list[dict[str, str]]:
    if per_class < 1:
        raise ValueError("per-class must be positive")
    groups: dict[str, list[dict[str, str]]] = {"0": [], "1": []}
    with manifest.open(newline="", encoding="utf-8") as stream:
        for row in csv.DictReader(stream):
            label = row.get("label")
            if label in groups:
                groups[label].append(row)
    selected: list[dict[str, str]] = []
    for label, values in groups.items():
        random.Random(seed + int(label)).shuffle(values)
        if len(values) < per_class:
            raise ValueError(
                f"{manifest} has only {len(values)} rows for label {label}; "
                f"need {per_class}"
            )
        selected.extend(values[:per_class])
    return selected


def score_rows(
    rows: list[dict[str, str]], detector: Any, frame_samples: int
) -> dict[str, Any]:
    if frame_samples < 1:
        raise ValueError("frame-samples must be positive")
    labels: list[int] = []
    scores: list[float] = []
    no_speech = 0
    window_count = 0
    for index, row in enumerate(rows, 1):
        audio, _ = decode_audio_file(row["path"], detector.sample_rate)
        session = StreamSession(
            detector=detector,
            sample_rate=detector.sample_rate,
            mode="evaluation",
            source="manifest",
        )
        for offset in range(0, audio.size, frame_samples):
            session.add_frame(audio[offset : offset + frame_samples])
        session.flush()
        summary = session.summary()
        window_count += len(summary["windows"])
        if summary["mean_prob"] is None:
            no_speech += 1
        else:
            labels.append(int(row["label"]))
            scores.append(float(summary["mean_prob"]))
        if index % 100 == 0 or index == len(rows):
            print(f"files_processed={index}/{len(rows)}", file=sys.stderr, flush=True)
    if not labels or len(set(labels)) != 2:
        raise ValueError("the selected samples must contain scored clips from both classes")
    return {
        "files_requested": len(rows),
        "files_scored": len(labels),
        "files_no_speech": no_speech,
        "stream_windows_scored": window_count,
        "labels": np.asarray(labels, dtype=np.int64),
        "scores": np.asarray(scores, dtype=np.float64),
    }


def report_metrics(result: dict[str, Any], threshold: float) -> dict[str, Any]:
    return classification_metrics(result["labels"], result["scores"], threshold)


def main() -> None:
    args = parse_args()
    if args.frame_samples < 1:
        raise SystemExit("--frame-samples must be positive")

    validation_rows = select_rows(args.validation_manifest, args.per_class, args.seed)
    test_rows = select_rows(args.test_manifest, args.per_class, args.seed)
    asvspoof = ASVspoofDetector()
    candidate = ASVspoofWindowAdapter(asvspoof)

    validation_candidate = score_rows(validation_rows, candidate, args.frame_samples)
    selected_threshold = threshold_at_eer(
        validation_candidate["labels"], validation_candidate["scores"]
    )
    validation_threshold_metrics = report_metrics(
        validation_candidate, selected_threshold
    )
    validation_artifact_threshold_metrics = report_metrics(
        validation_candidate, asvspoof.threshold
    )

    # The threshold is frozen from validation before any test scoring occurs.
    test_candidate = score_rows(test_rows, candidate, args.frame_samples)

    active_for = Detector()
    validation_active_for = score_rows(
        validation_rows, active_for, args.frame_samples
    )

    output = {
        "experiment": "ASVspoof complete-clip artifact applied to the live StreamSession window pipeline",
        "model_version": asvspoof.meta["model_version"],
        "validation_manifest": str(args.validation_manifest.resolve()),
        "test_manifest": str(args.test_manifest.resolve()),
        "sample_per_class_per_split": args.per_class,
        "seed": args.seed,
        "frame_samples": args.frame_samples,
        "window_seconds": candidate.window_seconds,
        "hop_seconds": 1.0,
        "demo_holdout_used": False,
        "threshold_source": "validation file-mean stream scores at equal error rate; frozen before test scoring",
        "validation": {
            "threshold": selected_threshold,
            "counts": {key: validation_candidate[key] for key in (
                "files_requested", "files_scored", "files_no_speech", "stream_windows_scored"
            )},
            "metrics_at_selected_threshold": validation_threshold_metrics,
            "metrics_at_artifact_complete_clip_threshold": validation_artifact_threshold_metrics,
        },
        "test": {
            "threshold": selected_threshold,
            "counts": {key: test_candidate[key] for key in (
                "files_requested", "files_scored", "files_no_speech", "stream_windows_scored"
            )},
            "metrics": report_metrics(test_candidate, selected_threshold),
        },
        "active_for_model_on_same_validation_sample": {
            "model_version": active_for.meta["model_version"],
            "threshold": active_for.threshold,
            "counts": {key: validation_active_for[key] for key in (
                "files_requested", "files_scored", "files_no_speech", "stream_windows_scored"
            )},
            "metrics": report_metrics(validation_active_for, active_for.threshold),
        },
        "limitation": "This is a balanced ASVspoof subset, not representative live-call evidence or a deployment approval.",
    }
    print(json.dumps(output, indent=2))


if __name__ == "__main__":
    main()

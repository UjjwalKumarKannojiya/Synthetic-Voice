"""Measure how well simple recording metadata predicts the fixed labels."""

from __future__ import annotations

import argparse
import csv
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score, confusion_matrix, f1_score, precision_score, recall_score
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.svf.audio_io import AudioConfig, load_audio


FEATURE_NAMES = ["duration_seconds", "sample_rate", "channels", "file_size_bytes", "rms", "silence_ratio"]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--silence-threshold", type=float, default=0.01)
    return parser.parse_args()


def metadata_features(row: dict[str, str], silence_threshold: float) -> list[float]:
    audio, _ = load_audio(row["path"], AudioConfig(sample_rate=int(row["sample_rate"])))
    rms = float(np.sqrt(np.mean(np.square(audio), dtype=np.float64))) if audio.size else 0.0
    silence_ratio = float(np.mean(np.abs(audio) <= silence_threshold)) if audio.size else 1.0
    return [
        float(row["duration_seconds"]),
        float(row["sample_rate"]),
        float(row["channels"]),
        float(row["file_size_bytes"]),
        rms,
        silence_ratio,
    ]


def load_split(manifest: Path, split: str, silence_threshold: float) -> tuple[np.ndarray, np.ndarray]:
    features: list[list[float]] = []
    labels: list[int] = []
    with manifest.open(newline="", encoding="utf-8") as stream:
        for row in csv.DictReader(stream):
            if row["split"] != split:
                continue
            features.append(metadata_features(row, silence_threshold))
            labels.append(int(row["label"]))
    if not features:
        raise ValueError(f"No rows found for split {split}")
    return np.asarray(features, dtype=np.float32), np.asarray(labels, dtype=np.int64)


def score(model: Pipeline, features: np.ndarray, labels: np.ndarray) -> dict[str, object]:
    predictions = model.predict(features)
    return {
        "accuracy": float(accuracy_score(labels, predictions)),
        "precision": float(precision_score(labels, predictions, zero_division=0)),
        "recall": float(recall_score(labels, predictions, zero_division=0)),
        "f1": float(f1_score(labels, predictions, zero_division=0)),
        "confusion_matrix": confusion_matrix(labels, predictions).tolist(),
        "count": int(labels.size),
    }


def main() -> None:
    args = parse_args()
    train_x, train_y = load_split(args.manifest, "training", args.silence_threshold)
    validation_x, validation_y = load_split(args.manifest, "validation", args.silence_threshold)
    test_x, test_y = load_split(args.manifest, "testing", args.silence_threshold)
    model = Pipeline(
        [
            ("scaler", StandardScaler()),
            ("classifier", LogisticRegression(max_iter=500, random_state=42)),
        ]
    )
    model.fit(train_x, train_y)
    report = {
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "experiment": "metadata_only_shortcut_baseline",
        "manifest": str(args.manifest.resolve()),
        "feature_names": FEATURE_NAMES,
        "silence_threshold": args.silence_threshold,
        "scaler_fit_split": "training",
        "metrics": {
            "validation": score(model, validation_x, validation_y),
            "test": score(model, test_x, test_y),
        },
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report["metrics"], indent=2))
    print(f"Saved result: {args.output}")


if __name__ == "__main__":
    main()
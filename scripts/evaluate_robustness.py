"""Evaluate the saved MFCC SVM under controlled test-only degradations."""

from __future__ import annotations

import argparse
import csv
import json
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path

import joblib
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.svf.audio_io import AudioConfig, load_audio
from src.svf.degrade.duration import center_crop_or_pad
from src.svf.degrade.noise import add_white_noise
from src.svf.degrade.telephone import telephone_bandlimit
from src.svf.eval.metrics import classification_metrics
from src.svf.features.mfcc import MFCCConfig, extract_mfcc, summarize_mfcc


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--model", type=Path, required=True)
    parser.add_argument("--baseline-results", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--max-files-per-class", type=int, default=50)
    parser.add_argument("--seed", type=int, default=42)
    return parser.parse_args()


def load_test_rows(manifest: Path, limit: int) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    counts = {0: 0, 1: 0}
    with manifest.open(newline="", encoding="utf-8") as stream:
        for row in csv.DictReader(stream):
            label = int(row["label"])
            if row["split"] != "testing" or counts[label] >= limit:
                continue
            rows.append(row)
            counts[label] += 1
            if counts[0] >= limit and counts[1] >= limit:
                break
    if len(rows) < limit * 2:
        raise ValueError(f"Expected {limit * 2} test rows, found {len(rows)}")
    return rows


def main() -> None:
    args = parse_args()
    model = joblib.load(args.model)
    baseline = json.loads(args.baseline_results.read_text(encoding="utf-8"))
    threshold = float(baseline["models"]["svm"]["test"]["threshold"])
    rows = load_test_rows(args.manifest, args.max_files_per_class)
    conditions: dict[str, callable] = {
        "clean": lambda audio, rate, index: audio,
        "noise_20db": lambda audio, rate, index: add_white_noise(audio, 20.0, args.seed + index),
        "noise_10db": lambda audio, rate, index: add_white_noise(audio, 10.0, args.seed + index),
        "noise_0db": lambda audio, rate, index: add_white_noise(audio, 0.0, args.seed + index),
        "telephone_simulated": lambda audio, rate, index: telephone_bandlimit(audio, rate),
        "duration_1s": lambda audio, rate, index: center_crop_or_pad(audio, rate, 1.0),
        "duration_2s": lambda audio, rate, index: center_crop_or_pad(audio, rate, 2.0),
        "duration_3s": lambda audio, rate, index: center_crop_or_pad(audio, rate, 3.0),
    }
    report: dict[str, object] = {
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "experiment": "test_only_robustness_mfcc_svm",
        "manifest": str(args.manifest.resolve()),
        "model": str(args.model.resolve()),
        "threshold": threshold,
        "threshold_source": "frozen_from_validation_eer_in_baseline_results",
        "max_files_per_class": args.max_files_per_class,
        "seed": args.seed,
        "compression": {"status": "not_run", "reason": "ffmpeg_available" if shutil.which("ffmpeg") else "ffmpeg_not_found"},
        "conditions": {},
    }
    for condition_name, transform in conditions.items():
        labels: list[int] = []
        scores: list[float] = []
        for index, row in enumerate(rows):
            audio, sample_rate = load_audio(row["path"], AudioConfig(sample_rate=int(row["sample_rate"])))
            degraded = np.asarray(transform(audio, sample_rate, index), dtype=np.float32)
            frames = extract_mfcc(degraded, MFCCConfig(sample_rate=sample_rate))
            vector = summarize_mfcc(frames).reshape(1, -1)
            labels.append(int(row["label"]))
            scores.append(float(model.predict_proba(vector)[0, 1]))
        report["conditions"][condition_name] = classification_metrics(
            np.asarray(labels), np.asarray(scores), threshold
        )
        print(f"{condition_name}: {report['conditions'][condition_name]}")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(f"Saved robustness report: {args.output}")


if __name__ == "__main__":
    main()
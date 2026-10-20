"""Train and evaluate an ASVspoof LA MFCC/SVM baseline."""

from __future__ import annotations

import argparse
import csv
import json
import random
import sys
from datetime import datetime, timezone
from pathlib import Path

import joblib
import numpy as np
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler
from sklearn.svm import SVC

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.svf.audio_io import AudioConfig, load_audio
from src.svf.eval.metrics import classification_metrics, threshold_at_eer
from src.svf.features.mfcc import MFCCConfig, extract_mfcc, summarize_mfcc


def read_rows(path: Path, max_per_class: int, seed: int) -> list[dict[str, str]]:
    with path.open(encoding="utf-8", newline="") as stream:
        rows = list(csv.DictReader(stream))
    grouped: dict[str, list[dict[str, str]]] = {"0": [], "1": []}
    for row in rows:
        grouped[row["label"]].append(row)
    selected: list[dict[str, str]] = []
    for label, group in grouped.items():
        rng = random.Random(seed + int(label))
        rng.shuffle(group)
        selected.extend(group[:max_per_class])
    return selected


def feature(row: dict[str, str]) -> np.ndarray:
    audio, sample_rate = load_audio(row["path"], AudioConfig(sample_rate=int(row["sr"])))
    frames = extract_mfcc(audio, MFCCConfig(sample_rate=sample_rate))
    return summarize_mfcc(frames).astype(np.float32, copy=False)


def matrix(rows: list[dict[str, str]], name: str) -> tuple[np.ndarray, np.ndarray]:
    values = []
    labels = []
    for index, row in enumerate(rows, 1):
        values.append(feature(row))
        labels.append(int(row["label"]))
        if index % 500 == 0 or index == len(rows):
            print(f"features_{name}={index}/{len(rows)}", flush=True)
    return np.stack(values), np.asarray(labels, dtype=np.int64)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest-dir", type=Path, default=Path("data/manifests"))
    parser.add_argument("--model-dir", type=Path, default=Path("models/asvspoof_la_svm"))
    parser.add_argument("--results", type=Path, default=Path("results/asvspoof_la_svm.json"))
    parser.add_argument("--max-files-per-class", type=int, default=500)
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()
    if args.max_files_per_class < 10:
        raise ValueError("--max-files-per-class must be at least 10")

    manifest_paths = {
        "train": args.manifest_dir / "asvspoof_la_train.csv",
        "val": args.manifest_dir / "asvspoof_la_val.csv",
        "test": args.manifest_dir / "asvspoof_la_test.csv",
    }
    rows = {
        split: read_rows(path, args.max_files_per_class, args.seed)
        for split, path in manifest_paths.items()
    }
    matrices = {split: matrix(value, split) for split, value in rows.items()}
    model = Pipeline([
        ("scaler", StandardScaler()),
        ("classifier", SVC(C=1.0, kernel="rbf", probability=True, class_weight="balanced", random_state=args.seed)),
    ])
    train_x, train_y = matrices["train"]
    val_x, val_y = matrices["val"]
    test_x, test_y = matrices["test"]
    model.fit(train_x, train_y)
    val_scores = model.predict_proba(val_x)[:, 1]
    test_scores = model.predict_proba(test_x)[:, 1]
    threshold = threshold_at_eer(val_y, val_scores)
    args.model_dir.mkdir(parents=True, exist_ok=True)
    model_path = args.model_dir / "svm.joblib"
    joblib.dump(model, model_path)

    score_path = args.results.with_name(args.results.stem + "_test_scores.csv")
    score_path.parent.mkdir(parents=True, exist_ok=True)
    with score_path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=["path", "label", "attack_id", "score"])
        writer.writeheader()
        writer.writerows({
            "path": row["path"],
            "label": row["label"],
            "attack_id": row["attack_id"],
            "score": float(score),
        } for row, score in zip(rows["test"], test_scores))

    report = {
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "dataset": "ASVspoof2019_LA",
        "seed": args.seed,
        "max_files_per_class": args.max_files_per_class,
        "feature": {"type": "MFCC + delta + delta-delta summary", "dimension": 120, "sample_rate": 16000},
        "threshold_source": "validation_eer",
        "threshold": float(threshold),
        "model_path": str(model_path.resolve()),
        "test_scores": str(score_path.resolve()),
        "demo_holdout_used": False,
        "validation": classification_metrics(val_y, val_scores, threshold),
        "test": classification_metrics(test_y, test_scores, threshold),
    }
    args.results.parent.mkdir(parents=True, exist_ok=True)
    args.results.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print("threshold=" + str(threshold))
    print("validation=" + json.dumps(report["validation"], sort_keys=True))
    print("test=" + json.dumps(report["test"], sort_keys=True))
    print("saved=" + str(args.results.resolve()))
    print("scores=" + str(score_path.resolve()))


if __name__ == "__main__":
    main()

"""Measure ASVspoof LA quality, metadata shortcuts, and class distributions."""

from __future__ import annotations

import argparse
import csv
import json
import random
import statistics
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import soundfile as sf
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (
    accuracy_score,
    confusion_matrix,
    f1_score,
    precision_score,
    recall_score,
    roc_auc_score,
)
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler


FIELDS = ["duration_s", "sr", "channels", "file_size_bytes", "rms", "silence_ratio"]
MANIFESTS = {
    "train": "asvspoof_la_train.csv",
    "val": "asvspoof_la_val.csv",
    "test": "asvspoof_la_test.csv",
    "demo_holdout": "asvspoof_la_demo_holdout.csv",
}


def rows_from(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8", newline="") as stream:
        return list(csv.DictReader(stream))


def sampled_rows(rows: list[dict[str, str]], max_per_class: int, seed: int) -> list[dict[str, str]]:
    grouped: defaultdict[str, list[dict[str, str]]] = defaultdict(list)
    for row in rows:
        grouped[row["label"]].append(row)
    selected: list[dict[str, str]] = []
    for label, group in sorted(grouped.items()):
        rng = random.Random(seed + int(label))
        rng.shuffle(group)
        selected.extend(group[:max_per_class])
    return selected


def audio_features(row: dict[str, str], silence_threshold: float) -> list[float]:
    audio, sample_rate = sf.read(row["path"], dtype="float32", always_2d=False)
    if audio.ndim != 1:
        audio = np.mean(audio, axis=1)
    if not np.isfinite(audio).all():
        raise ValueError(f"non-finite audio: {row['path']}")
    rms = float(np.sqrt(np.mean(np.square(audio), dtype=np.float64))) if audio.size else 0.0
    silence_ratio = float(np.mean(np.abs(audio) <= silence_threshold)) if audio.size else 1.0
    return [
        float(row["duration_s"]),
        float(sample_rate),
        1.0,
        float(Path(row["path"]).stat().st_size),
        rms,
        silence_ratio,
    ]


def summarize(values: list[float]) -> dict[str, float | int | None]:
    if not values:
        return {"count": 0, "min": None, "mean": None, "median": None, "p95": None, "max": None}
    ordered = sorted(values)
    return {
        "count": len(values),
        "min": float(ordered[0]),
        "mean": float(statistics.fmean(values)),
        "median": float(statistics.median(values)),
        "p95": float(np.percentile(ordered, 95)),
        "max": float(ordered[-1]),
    }


def metrics(model: Pipeline, x: np.ndarray, y: np.ndarray) -> dict[str, object]:
    prediction = model.predict(x)
    score = model.predict_proba(x)[:, 1]
    return {
        "count": int(y.size),
        "accuracy": float(accuracy_score(y, prediction)),
        "precision": float(precision_score(y, prediction, zero_division=0)),
        "recall": float(recall_score(y, prediction, zero_division=0)),
        "f1": float(f1_score(y, prediction, zero_division=0)),
        "roc_auc": float(roc_auc_score(y, score)),
        "confusion_matrix": confusion_matrix(y, prediction).tolist(),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest-dir", type=Path, default=Path("data/manifests"))
    parser.add_argument("--output", type=Path, default=Path("results/asvspoof_la_data_quality.json"))
    parser.add_argument("--plot-dir", type=Path, default=Path("results/asvspoof_la_plots"))
    parser.add_argument("--max-files-per-class", type=int, default=1000)
    parser.add_argument("--silence-threshold", type=float, default=0.01)
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()
    if args.max_files_per_class < 10:
        raise ValueError("--max-files-per-class must be at least 10")

    all_rows = {split: rows_from(args.manifest_dir / filename) for split, filename in MANIFESTS.items()}
    class_balance = {
        split: dict(Counter(row["label"] for row in rows))
        for split, rows in all_rows.items()
    }
    sampled = {
        split: sampled_rows(rows, args.max_files_per_class, args.seed)
        for split, rows in all_rows.items()
        if split != "demo_holdout"
    }
    features: dict[str, np.ndarray] = {}
    labels: dict[str, np.ndarray] = {}
    distributions: dict[str, dict[str, dict[str, object]]] = {}
    for split, rows in sampled.items():
        matrix = np.asarray([audio_features(row, args.silence_threshold) for row in rows], dtype=np.float32)
        target = np.asarray([int(row["label"]) for row in rows], dtype=np.int64)
        features[split] = matrix
        labels[split] = target
        distributions[split] = {}
        for label in (0, 1):
            mask = target == label
            distributions[split][f"label_{label}"] = {
                name: summarize(matrix[mask, index].tolist())
                for index, name in enumerate(FIELDS)
            }

    model = Pipeline([
        ("scaler", StandardScaler()),
        ("classifier", LogisticRegression(max_iter=500, random_state=args.seed)),
    ])
    model.fit(features["train"], labels["train"])
    shortcut = {
        split: metrics(model, features[split], labels[split])
        for split in ("val", "test")
    }

    args.plot_dir.mkdir(parents=True, exist_ok=True)
    for index, name in enumerate(("duration_s", "rms", "silence_ratio")):
        figure, axis = plt.subplots(figsize=(8, 4))
        for split in ("train", "val", "test"):
            for label, color in ((0, "tab:blue"), (1, "tab:orange")):
                values = features[split][labels[split] == label, index]
                axis.hist(values, bins=40, alpha=0.35, color=color, label=f"{split} label={label}", density=True)
        axis.set_title(f"ASVspoof LA {name} distributions (sampled)")
        axis.set_xlabel(name)
        axis.set_ylabel("density")
        axis.legend(fontsize=7)
        figure.tight_layout()
        figure.savefig(args.plot_dir / f"{name}.png", dpi=120)
        plt.close(figure)

    report = {
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "experiment": "asvspoof_la_data_quality_and_metadata_shortcut",
        "manifest_dir": str(args.manifest_dir.resolve()),
        "seed": args.seed,
        "max_files_per_class": args.max_files_per_class,
        "silence_threshold": args.silence_threshold,
        "class_balance_full_manifests": class_balance,
        "sampled_counts": {split: int(rows.__len__()) for split, rows in sampled.items()},
        "distributions": distributions,
        "shortcut_baseline": {
            "features": FIELDS,
            "scaler_fit_split": "train",
            "metrics": shortcut,
        },
        "demo_holdout_not_used": True,
        "plots": [str(path.resolve()) for path in sorted(args.plot_dir.glob("*.png"))],
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print("class_balance_full_manifests=" + json.dumps(class_balance, sort_keys=True))
    print("sampled_counts=" + json.dumps(report["sampled_counts"], sort_keys=True))
    print("shortcut_metrics=" + json.dumps(shortcut, sort_keys=True))
    print("plots=" + json.dumps(report["plots"]))
    print("saved=" + str(args.output.resolve()))


if __name__ == "__main__":
    main()

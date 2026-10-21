"""Evaluate the frozen ASVspoof clip model on a separate labeled manifest split."""

from __future__ import annotations

import argparse
import csv
import json
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np
from sklearn.metrics import roc_auc_score

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.core.asvspoof_detector import ASVspoofDetector
from app.core.audio_utils import decode_audio_file


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--manifest", type=Path, required=True,
        help="Labeled CSV with path, label, split, and optional dataset_variant columns.",
    )
    parser.add_argument("--split", required=True, help="Manifest split to score.")
    parser.add_argument("--uncertain-band", type=float, required=True)
    parser.add_argument(
        "--model-meta", type=Path,
        default=ROOT / "models" / "asvspoof_la_svm_balanced2500" / "model_meta.json",
    )
    parser.add_argument("--previously-screened", action="store_true")
    parser.add_argument(
        "--output", type=Path, default=None,
        help="Optional new report path; existing files are never overwritten.",
    )
    return parser.parse_args()


def confusion_metrics(labels: np.ndarray, scores: np.ndarray, threshold: float) -> dict[str, Any]:
    predicted = (scores >= threshold).astype(np.int64)
    tn = int(np.sum((labels == 0) & (predicted == 0)))
    fp = int(np.sum((labels == 0) & (predicted == 1)))
    fn = int(np.sum((labels == 1) & (predicted == 0)))
    tp = int(np.sum((labels == 1) & (predicted == 1)))
    return {
        "threshold": threshold,
        "accuracy": (tn + tp) / int(labels.size),
        "fpr": fp / (fp + tn) if fp + tn else None,
        "fnr": fn / (fn + tp) if fn + tp else None,
        "roc_auc": float(roc_auc_score(labels, scores)) if len(np.unique(labels)) == 2 else None,
        "confusion_matrix_labels_0_1": [[tn, fp], [fn, tp]],
    }


def main() -> None:
    args = parse_args()
    if not 0.0 <= args.uncertain_band <= 1.0:
        raise ValueError("--uncertain-band must be between 0 and 1")
    if not args.manifest.is_file():
        raise FileNotFoundError(args.manifest)

    with args.manifest.open(encoding="utf-8", newline="") as stream:
        rows = [
            row for row in csv.DictReader(stream)
            if row.get("split") == args.split and row.get("label") in {"0", "1"}
        ]
    if not rows:
        raise ValueError(f"No labeled rows found for split {args.split!r}")

    detector = ASVspoofDetector(meta_path=args.model_meta)
    labels: list[int] = []
    scores: list[float] = []
    unscored: Counter[str] = Counter()
    verdicts: dict[str, Counter[str]] = {"0": Counter(), "1": Counter()}
    lower = max(0.0, detector.threshold - args.uncertain_band)
    upper = min(1.0, detector.threshold + args.uncertain_band)
    for index, row in enumerate(rows, 1):
        audio, sample_rate = decode_audio_file(row["path"], detector.sample_rate)
        result = detector.analyze_array(audio, sample_rate)
        label = row["label"]
        if result["mean_prob"] is None:
            unscored[label] += 1
        else:
            score = float(result["mean_prob"])
            labels.append(int(label))
            scores.append(score)
            if score < lower:
                verdicts[label]["likely_real"] += 1
            elif score > upper:
                verdicts[label]["likely_synthetic"] += 1
            else:
                verdicts[label]["uncertain"] += 1
        if index % 100 == 0 or index == len(rows):
            print(f"files_processed={index}/{len(rows)}", file=sys.stderr, flush=True)

    label_array = np.asarray(labels, dtype=np.int64)
    score_array = np.asarray(scores, dtype=np.float64)
    if label_array.size == 0:
        raise ValueError("No files received a model score; external evaluation is unavailable")
    report = {
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "experiment": "frozen_asvspoof_complete_clip_external_diagnostic",
        "manifest": str(args.manifest.resolve()),
        "split": args.split,
        "dataset_variants": sorted({row.get("dataset_variant", "unknown") for row in rows}),
        "model_version": detector.meta["model_version"],
        "labels": {"0": "bona fide", "1": "spoof"},
        "files_requested": len(rows),
        "files_requested_by_label": dict(sorted(Counter(row["label"] for row in rows).items())),
        "files_scored": int(label_array.size),
        "unscored_by_label": {"0": unscored["0"], "1": unscored["1"]},
        "threshold_source": detector.meta["threshold_source"],
        "threshold_selection_on_this_split": False,
        "threshold": detector.threshold,
        "uncertain_band": args.uncertain_band,
        "metrics_at_frozen_artifact_threshold": confusion_metrics(label_array, score_array, detector.threshold),
        "default_verdict_counts_by_true_label": {
            "0_bona_fide": dict(verdicts["0"]),
            "1_spoof": dict(verdicts["1"]),
        },
        "split_previously_screened_during_development": args.previously_screened,
        "locked_demo_holdout_used": False,
        "interpretation_limits": [
            "This is a cross-dataset diagnostic, not evidence of real-world accuracy.",
            "Do not select or tune a threshold from this split.",
            "The score is an estimated class-1 spoof score, not a calibrated real-world probability.",
        ],
    }
    output = json.dumps(report, indent=2)
    if args.output is None:
        print(output)
        return
    report_path = args.output.resolve()
    if report_path.exists():
        raise FileExistsError(f"Refusing to overwrite report: {report_path}")
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(output + "\n", encoding="utf-8")
    print(f"saved_report={report_path}")
    print(output)


if __name__ == "__main__":
    main()

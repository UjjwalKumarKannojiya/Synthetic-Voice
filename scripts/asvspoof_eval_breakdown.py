"""Evaluate ASVspoof scores by attack ID and known/unknown attack group."""

from __future__ import annotations

import argparse
import csv
import json
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
from sklearn.metrics import (
    accuracy_score,
    confusion_matrix,
    f1_score,
    precision_score,
    recall_score,
    roc_auc_score,
)


KNOWN_ATTACKS = {"A01", "A02", "A03", "A04", "A05", "A06"}


def load_scores(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8", newline="") as stream:
        rows = list(csv.DictReader(stream))
    required = {"path", "label", "attack_id", "score"}
    if not rows or set(rows[0]) < required:
        raise ValueError(f"{path} must contain columns {sorted(required)}")
    for row in rows:
        score = float(row["score"])
        if not 0.0 <= score <= 1.0:
            raise ValueError(f"score outside [0, 1] for {row['path']}")
    return rows


def eer(labels: np.ndarray, scores: np.ndarray) -> float | None:
    positives = scores[labels == 1]
    negatives = scores[labels == 0]
    if not len(positives) or not len(negatives):
        return None
    thresholds = np.unique(scores)
    rates = []
    for threshold in thresholds:
        predicted = scores >= threshold
        fpr = float(np.mean(predicted[labels == 0]))
        fnr = float(np.mean(~predicted[labels == 1]))
        rates.append((abs(fpr - fnr), (fpr + fnr) / 2.0))
    return min(rates)[1]


def group_metrics(rows: list[dict[str, str]], threshold: float) -> dict[str, object]:
    labels = np.asarray([int(row["label"]) for row in rows], dtype=np.int64)
    scores = np.asarray([float(row["score"]) for row in rows], dtype=np.float64)
    predictions = scores >= threshold
    result: dict[str, object] = {
        "count": int(labels.size),
        "bona_fide": int(np.sum(labels == 0)),
        "spoof": int(np.sum(labels == 1)),
        "threshold": threshold,
        "accuracy": float(accuracy_score(labels, predictions)),
        "precision": float(precision_score(labels, predictions, zero_division=0)),
        "recall": float(recall_score(labels, predictions, zero_division=0)),
        "f1": float(f1_score(labels, predictions, zero_division=0)),
        "confusion_matrix": confusion_matrix(labels, predictions, labels=[0, 1]).tolist(),
        "eer": eer(labels, scores),
    }
    result["roc_auc"] = float(roc_auc_score(labels, scores)) if len(np.unique(labels)) == 2 else None
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--scores", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--threshold", type=float, required=True)
    args = parser.parse_args()
    if not 0.0 <= args.threshold <= 1.0:
        raise ValueError("--threshold must be between 0 and 1")

    rows = load_scores(args.scores)
    by_attack: defaultdict[str, list[dict[str, str]]] = defaultdict(list)
    for row in rows:
        if row["label"] == "0" and row["attack_id"] != "-":
            raise ValueError(f"bona fide row has attack ID {row['attack_id']}")
        if row["label"] == "1" and row["attack_id"] == "-":
            raise ValueError(f"spoof row has no attack ID: {row['path']}")
        by_attack[row["attack_id"]].append(row)

    known_rows = [row for row in rows if row["label"] == "0" or row["attack_id"] in KNOWN_ATTACKS]
    unknown_rows = [row for row in rows if row["label"] == "0" or row["attack_id"] not in KNOWN_ATTACKS]
    report = {
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "scores": str(args.scores.resolve()),
        "threshold": args.threshold,
        "known_attack_ids": sorted(KNOWN_ATTACKS),
        "min_tdcf": {"computed": False, "reason": "ASV speaker-verification scores are not provided"},
        "overall": group_metrics(rows, args.threshold),
        "by_attack_id": {
            attack: group_metrics(group, args.threshold)
            for attack, group in sorted(by_attack.items())
        },
        "known_attacks": group_metrics(known_rows, args.threshold),
        "unknown_attacks": group_metrics(unknown_rows, args.threshold),
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print("overall=" + json.dumps(report["overall"], sort_keys=True))
    print("attack_ids=" + ",".join(report["by_attack_id"]))
    print("known=" + json.dumps(report["known_attacks"], sort_keys=True))
    print("unknown=" + json.dumps(report["unknown_attacks"], sort_keys=True))
    print("min_tdcf=not_computed reason=ASV speaker-verification scores are not provided")
    print("saved=" + str(args.output.resolve()))


if __name__ == "__main__":
    main()

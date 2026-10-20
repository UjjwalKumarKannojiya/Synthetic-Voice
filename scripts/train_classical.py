"""Train SVM and Random Forest baselines from a cached feature index."""

from __future__ import annotations

import argparse
import csv
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import joblib
import numpy as np
from sklearn.ensemble import RandomForestClassifier
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler
from sklearn.svm import SVC

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.svf.eval.metrics import classification_metrics, threshold_at_eer


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--feature-index", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--results", type=Path, required=True)
    parser.add_argument("--seed", type=int, default=42)
    return parser.parse_args()


def load_features(index_path: Path) -> dict[str, tuple[np.ndarray, np.ndarray]]:
    grouped: dict[str, list[tuple[np.ndarray, int]]] = {"training": [], "validation": [], "testing": []}
    with index_path.open(newline="", encoding="utf-8") as stream:
        for row in csv.DictReader(stream):
            vector = np.load(row["feature_path"], allow_pickle=False).astype(np.float32, copy=False)
            grouped[row["split"]].append((vector, int(row["label"])))
    return {
        split: (np.stack([item[0] for item in values]), np.asarray([item[1] for item in values], dtype=np.int64))
        for split, values in grouped.items()
    }


def main() -> None:
    args = parse_args()
    data = load_features(args.feature_index)
    train_x, train_y = data["training"]
    validation_x, validation_y = data["validation"]
    test_x, test_y = data["testing"]
    models = {
        "svm": Pipeline(
            [
                ("scaler", StandardScaler()),
                ("classifier", SVC(C=1.0, kernel="rbf", probability=True, random_state=args.seed)),
            ]
        ),
        "random_forest": RandomForestClassifier(
            n_estimators=200, random_state=args.seed, n_jobs=-1, class_weight="balanced"
        ),
    }
    args.output_dir.mkdir(parents=True, exist_ok=True)
    report: dict[str, object] = {
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "feature_index": str(args.feature_index.resolve()),
        "seed": args.seed,
        "threshold_source": "validation_eer",
        "models": {},
    }
    for model_name, model in models.items():
        model.fit(train_x, train_y)
        validation_scores = model.predict_proba(validation_x)[:, 1]
        test_scores = model.predict_proba(test_x)[:, 1]
        threshold = threshold_at_eer(validation_y, validation_scores)
        model_path = args.output_dir / f"{model_name}.joblib"
        joblib.dump(model, model_path)
        report["models"][model_name] = {
            "model_path": str(model_path.resolve()),
            "validation": classification_metrics(validation_y, validation_scores, threshold),
            "test": classification_metrics(test_y, test_scores, threshold),
        }
        print(f"{model_name}: test={report['models'][model_name]['test']}")
    args.results.parent.mkdir(parents=True, exist_ok=True)
    report_path = args.results
    report_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(f"Saved results: {report_path}")


if __name__ == "__main__":
    main()
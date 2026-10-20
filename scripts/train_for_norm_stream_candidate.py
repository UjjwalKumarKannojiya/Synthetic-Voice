"""Train and evaluate an isolated 2-second FoR stream-model candidate.

The active model is never modified. Matching basenames are assigned to one split
with test taking priority, then validation, then training, to reduce likely source
recording overlap when speaker IDs are absent.
"""

from __future__ import annotations

import argparse
import csv
import json
import random
import sys
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import joblib
import numpy as np
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler
from sklearn.svm import SVC

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.core.detector import Detector, DetectorConfig
from app.core.streaming import StreamSession
from src.svf.audio_io import AudioConfig, load_audio
from src.svf.degrade.duration import center_crop_or_pad
from src.svf.eval.metrics import classification_metrics, threshold_at_eer
from src.svf.features.mfcc import MFCCConfig, extract_mfcc, summarize_mfcc


SPLIT_PRIORITY = {"training": 0, "validation": 1, "testing": 2}
FRAME_SAMPLES = 4096
WINDOW_SECONDS = 2.0
HOP_SECONDS = 1.0
MODEL_C_VALUES = (0.1, 1.0, 10.0)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--manifest",
        type=Path,
        default=ROOT / "data" / "manifests" / "for_norm_clean.csv",
    )
    parser.add_argument("--train-per-class", type=int, default=5000)
    parser.add_argument("--validation-per-class", type=int, default=1000)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--output-name", default="for_norm_stream_seed42")
    return parser.parse_args()


def assign_filename_groups(manifest: Path) -> dict[str, list[list[dict[str, str]]]]:
    grouped: dict[str, list[dict[str, str]]] = defaultdict(list)
    with manifest.open(newline="", encoding="utf-8") as stream:
        for row in csv.DictReader(stream):
            if row.get("split") not in SPLIT_PRIORITY or row.get("label") not in {"0", "1"}:
                continue
            key = Path(row["path"]).name.casefold()
            grouped[key].append(row)

    assigned: dict[str, list[list[dict[str, str]]]] = {
        split: [] for split in SPLIT_PRIORITY
    }
    for rows in grouped.values():
        owner = max(
            {row["split"] for row in rows}, key=lambda split: SPLIT_PRIORITY[split]
        )
        owned_rows = [row for row in rows if row["split"] == owner]
        if owned_rows:
            assigned[owner].append(owned_rows)
    return assigned


def choose_grouped_rows(
    groups: list[list[dict[str, str]]], per_class: int, seed: int
) -> list[dict[str, str]]:
    if per_class < 1:
        raise ValueError("per-class sample count must be positive")
    shuffled = list(groups)
    random.Random(seed).shuffle(shuffled)
    selected: list[dict[str, str]] = []
    counts: Counter[int] = Counter()
    for group in shuffled:
        group_counts = Counter(int(row["label"]) for row in group)
        if any(counts[label] + group_counts[label] > per_class for label in (0, 1)):
            continue
        selected.extend(group)
        counts.update(group_counts)
        if counts[0] == per_class and counts[1] == per_class:
            break
    if counts[0] < per_class or counts[1] < per_class:
        raise ValueError(
            f"Could not select the requested grouped sample; selected labels {dict(counts)}"
        )
    return selected


def ensure_disjoint_filenames(splits: dict[str, list[dict[str, str]]]) -> None:
    names = {
        split: {Path(row["path"]).name.casefold() for row in rows}
        for split, rows in splits.items()
    }
    for first, second in (("training", "validation"), ("training", "testing"), ("validation", "testing")):
        overlap = names[first] & names[second]
        if overlap:
            raise ValueError(f"filename-group leakage remains between {first} and {second}")


def load_model_audio(row: dict[str, str], sample_rate: int) -> np.ndarray:
    audio, actual_rate = load_audio(
        row["path"], AudioConfig(sample_rate=sample_rate)
    )
    if actual_rate != sample_rate:
        raise ValueError(f"expected {sample_rate} Hz, got {actual_rate} Hz")
    return audio


def feature_vector(audio: np.ndarray, config: MFCCConfig) -> np.ndarray:
    fixed = center_crop_or_pad(audio, config.sample_rate, WINDOW_SECONDS)
    return summarize_mfcc(extract_mfcc(fixed, config))


def build_training_matrix(
    rows: list[dict[str, str]], config: MFCCConfig
) -> tuple[np.ndarray, np.ndarray]:
    features: list[np.ndarray] = []
    labels: list[int] = []
    for index, row in enumerate(rows, 1):
        audio = load_model_audio(row, config.sample_rate)
        features.append(feature_vector(audio, config))
        labels.append(int(row["label"]))
        if index % 500 == 0 or index == len(rows):
            print(f"training_features={index}/{len(rows)}", file=sys.stderr, flush=True)
    return np.stack(features), np.asarray(labels, dtype=np.int64)


class WindowFeatureCollector:
    """Collect speech-window features using the app's exact stream segmentation."""

    def __init__(self, config: MFCCConfig, threshold: float = 0.5) -> None:
        self.sample_rate = config.sample_rate
        self.window_seconds = WINDOW_SECONDS
        self.window_samples = round(self.window_seconds * self.sample_rate)
        self.hop_samples = round(HOP_SECONDS * self.sample_rate)
        self.threshold = threshold
        self.config = DetectorConfig(
            hop_seconds=HOP_SECONDS, threshold=threshold
        )
        self.mfcc_config = config
        self.features: list[np.ndarray] = []

    def predict_window(self, audio: np.ndarray, sample_rate: int) -> float:
        if sample_rate != self.sample_rate:
            raise ValueError(f"expected {self.sample_rate} Hz audio, got {sample_rate} Hz")
        self.features.append(
            summarize_mfcc(extract_mfcc(audio, self.mfcc_config))
        )
        return 0.5


def collect_validation_windows(
    rows: list[dict[str, str]], config: MFCCConfig
) -> tuple[list[tuple[int, np.ndarray]], dict[str, int]]:
    examples: list[tuple[int, np.ndarray]] = []
    no_speech = 0
    window_count = 0
    for index, row in enumerate(rows, 1):
        collector = WindowFeatureCollector(config)
        session = StreamSession(
            collector, collector.sample_rate, "evaluation", "manifest"
        )
        audio = load_model_audio(row, collector.sample_rate)
        for offset in range(0, audio.size, FRAME_SAMPLES):
            session.add_frame(audio[offset : offset + FRAME_SAMPLES])
        session.flush()
        window_count += len(collector.features)
        if collector.features:
            examples.append(
                (int(row["label"]), np.stack(collector.features))
            )
        else:
            no_speech += 1
        if index % 200 == 0 or index == len(rows):
            print(f"validation_stream_features={index}/{len(rows)}", file=sys.stderr, flush=True)
    if not examples or len({label for label, _ in examples}) != 2:
        raise ValueError("validation must contain speech windows from both classes")
    return examples, {
        "files_requested": len(rows),
        "files_scored": len(examples),
        "files_no_speech": no_speech,
        "stream_windows_scored": window_count,
    }


def aggregate_file_scores(
    model: Pipeline, examples: list[tuple[int, np.ndarray]]
) -> tuple[np.ndarray, np.ndarray]:
    labels: list[int] = []
    scores: list[float] = []
    for label, windows in examples:
        window_scores = model.predict_proba(windows)[:, 1]
        labels.append(label)
        scores.append(float(np.mean(window_scores)))
    return np.asarray(labels, dtype=np.int64), np.asarray(scores, dtype=np.float64)


class ModelWindowScorer:
    """Runtime-compatible scorer for an isolated candidate model."""

    def __init__(
        self, model: Pipeline, config: MFCCConfig, threshold: float, uncertain_band: float
    ) -> None:
        self.model = model
        self.mfcc_config = config
        self.sample_rate = config.sample_rate
        self.window_seconds = WINDOW_SECONDS
        self.window_samples = round(self.window_seconds * self.sample_rate)
        self.hop_samples = round(HOP_SECONDS * self.sample_rate)
        self.threshold = threshold
        self.config = DetectorConfig(
            hop_seconds=HOP_SECONDS,
            uncertain_band=uncertain_band,
            threshold=threshold,
        )

    def predict_window(self, audio: np.ndarray, sample_rate: int) -> float:
        if sample_rate != self.sample_rate:
            raise ValueError(f"expected {self.sample_rate} Hz audio, got {sample_rate} Hz")
        vector = summarize_mfcc(extract_mfcc(audio, self.mfcc_config)).reshape(1, -1)
        return float(self.model.predict_proba(vector)[0, 1])


def evaluate_test_stream(
    rows: list[dict[str, str]],
    candidate: ModelWindowScorer,
    active: Detector,
) -> dict[str, Any]:
    candidate_labels: list[int] = []
    candidate_scores: list[float] = []
    active_labels: list[int] = []
    active_scores: list[float] = []
    no_speech = 0
    window_count = 0
    for index, row in enumerate(rows, 1):
        audio = load_model_audio(row, candidate.sample_rate)
        candidate_session = StreamSession(
            candidate, candidate.sample_rate, "evaluation", "manifest"
        )
        active_session = StreamSession(
            active, active.sample_rate, "evaluation", "manifest"
        )
        for offset in range(0, audio.size, FRAME_SAMPLES):
            frame = audio[offset : offset + FRAME_SAMPLES]
            candidate_session.add_frame(frame)
            active_session.add_frame(frame)
        candidate_session.flush()
        active_session.flush()
        candidate_summary = candidate_session.summary()
        active_summary = active_session.summary()
        window_count += len(candidate_summary["windows"])
        if candidate_summary["mean_prob"] is None:
            no_speech += 1
        else:
            candidate_labels.append(int(row["label"]))
            candidate_scores.append(float(candidate_summary["mean_prob"]))
            if active_summary["mean_prob"] is not None:
                active_labels.append(int(row["label"]))
                active_scores.append(float(active_summary["mean_prob"]))
        if index % 200 == 0 or index == len(rows):
            print(f"test_stream_files={index}/{len(rows)}", file=sys.stderr, flush=True)

    labels_array = np.asarray(candidate_labels, dtype=np.int64)
    scores_array = np.asarray(candidate_scores, dtype=np.float64)
    return {
        "counts": {
            "files_requested": len(rows),
            "files_scored": len(candidate_labels),
            "files_no_speech": no_speech,
            "stream_windows_scored": window_count,
        },
        "candidate_metrics": classification_metrics(
            labels_array, scores_array, candidate.threshold
        ),
        "active_model_counts": {
            "files_scored": len(active_labels),
            "files_no_speech": len(rows) - len(active_labels),
        },
        "active_model_metrics": classification_metrics(
            np.asarray(active_labels, dtype=np.int64),
            np.asarray(active_scores, dtype=np.float64),
            active.threshold,
        ),
    }


def main() -> None:
    args = parse_args()
    if args.train_per_class < 100 or args.validation_per_class < 50:
        raise SystemExit("sample sizes are too small for a useful candidate screen")
    if not args.output_name or Path(args.output_name).name != args.output_name:
        raise SystemExit("output-name must be a single path component")

    output_dir = ROOT / "models" / "candidates" / args.output_name
    report_path = ROOT / "results" / "candidates" / f"{args.output_name}.json"
    if output_dir.exists() or report_path.exists():
        raise FileExistsError(
            f"Refusing to overwrite candidate outputs: {output_dir} or {report_path}"
        )

    assigned = assign_filename_groups(args.manifest)
    train_rows = choose_grouped_rows(
        assigned["training"], args.train_per_class, args.seed
    )
    validation_rows = choose_grouped_rows(
        assigned["validation"], args.validation_per_class, args.seed + 1
    )
    test_rows = [row for group in assigned["testing"] for row in group]
    split_rows = {
        "training": train_rows,
        "validation": validation_rows,
        "testing": test_rows,
    }
    ensure_disjoint_filenames(split_rows)

    active = Detector()
    mfcc = active.mfcc_config
    train_x, train_y = build_training_matrix(train_rows, mfcc)
    validation_examples, validation_counts = collect_validation_windows(
        validation_rows, mfcc
    )
    validation_labels = np.asarray(
        [label for label, _ in validation_examples], dtype=np.int64
    )

    candidate_scores: dict[str, dict[str, Any]] = {}
    selected: tuple[float, Pipeline, float, dict[str, Any], np.ndarray] | None = None
    for c_value in MODEL_C_VALUES:
        pipeline = Pipeline(
            [
                ("scaler", StandardScaler()),
                (
                    "classifier",
                    SVC(
                        C=c_value,
                        kernel="rbf",
                        probability=True,
                        class_weight="balanced",
                        random_state=args.seed,
                    ),
                ),
            ]
        )
        pipeline.fit(train_x, train_y)
        labels, val_scores = aggregate_file_scores(pipeline, validation_examples)
        threshold = threshold_at_eer(labels, val_scores)
        metrics = classification_metrics(labels, val_scores, threshold)
        candidate_scores[str(c_value)] = {
            "threshold": threshold,
            "validation_metrics": metrics,
        }
        print(
            f"validation_c={c_value} eer={metrics['eer']:.6f} threshold={threshold:.6f}",
            file=sys.stderr,
            flush=True,
        )
        if selected is None or float(metrics["eer"]) < selected[0]:
            selected = (float(metrics["eer"]), pipeline, threshold, metrics, val_scores)

    if selected is None:
        raise RuntimeError("no candidate model was trained")
    selected_eer, selected_model, selected_threshold, selected_val_metrics, _ = selected
    candidate_scorer = ModelWindowScorer(
        selected_model,
        mfcc,
        selected_threshold,
        active.config.uncertain_band,
    )
    test_result = evaluate_test_stream(test_rows, candidate_scorer, active)

    output_dir.mkdir(parents=True)
    model_path = output_dir / "svm.joblib"
    metadata_path = output_dir / "model_meta.json"
    joblib.dump(selected_model, model_path)
    metadata = {
        "name": args.output_name,
        "model_path": "svm.joblib",
        "model_version": args.output_name,
        "training_dataset": "for-norm-clean",
        "sample_rate": active.sample_rate,
        "window_seconds": WINDOW_SECONDS,
        "threshold": selected_threshold,
        "threshold_source": "group-disjoint validation stream file-mean EER",
        "score_definition": "scikit-learn SVC predict_proba class-1 estimated fake score; not calibrated real-world probability",
        "mfcc": active.meta["mfcc"],
        "training_protocol": {
            "manifest": str(args.manifest.resolve()),
            "group_key": "case-folded audio basename",
            "group_assignment_priority": ["testing", "validation", "training"],
            "train_per_class_target": args.train_per_class,
            "validation_per_class_target": args.validation_per_class,
            "training_rows": len(train_rows),
            "validation_rows": len(validation_rows),
            "testing_rows": len(test_rows),
            "seed": args.seed,
            "selected_c": float(selected_model.named_steps["classifier"].C),
        },
    }
    metadata_path.write_text(json.dumps(metadata, indent=2), encoding="utf-8")

    def label_counts(rows: list[dict[str, str]]) -> dict[str, int]:
        return dict(sorted(Counter(row["label"] for row in rows).items()))

    report = {
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "experiment": "isolated_for_norm_stream_candidate",
        "manifest": str(args.manifest.resolve()),
        "grouping": "case-folded basename; test owns shared groups, then validation, then training",
        "demo_holdout_used": False,
        "seed": args.seed,
        "feature": "20 MFCC + delta + delta-delta mean/std; center crop or zero pad to 2 seconds",
        "stream_validation": {
            "window_seconds": WINDOW_SECONDS,
            "hop_seconds": HOP_SECONDS,
            "frame_samples": FRAME_SAMPLES,
            "threshold_source": "validation file-mean stream score EER",
            "files_per_class_target": args.validation_per_class,
            "files_by_label": label_counts(validation_rows),
            "counts": validation_counts,
            "candidates_by_c": candidate_scores,
            "selected_validation_eer": selected_eer,
            "selected_validation_metrics": selected_val_metrics,
        },
        "training": {
            "files_per_class_target": args.train_per_class,
            "files_by_label": label_counts(train_rows),
            "feature_count": int(train_x.shape[1]),
        },
        "test_stream": {
            "threshold_frozen_from_validation": selected_threshold,
            **test_result,
        },
        "model_path": str(model_path.resolve()),
        "metadata_path": str(metadata_path.resolve()),
        "limitations": [
            "Speaker and generator identifiers are absent; filename grouping is only a conservative proxy.",
            "Results describe this local dataset and do not establish performance on live calls or unseen generators.",
            "This candidate was not activated in the application.",
        ],
    }
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2))
    print(f"saved_model={model_path}")
    print(f"saved_report={report_path}")


if __name__ == "__main__":
    main()

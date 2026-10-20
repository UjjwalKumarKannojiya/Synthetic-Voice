"""Evaluate a frozen FoR stream candidate on the for-rerec test partition."""

from __future__ import annotations

import argparse
import csv
import json
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import joblib

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.core.detector import Detector
from scripts.train_for_norm_stream_candidate import ModelWindowScorer, evaluate_test_stream
from src.svf.features.mfcc import MFCCConfig


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--manifest", type=Path, default=ROOT / "data" / "manifests" / "for_rerec.csv"
    )
    parser.add_argument(
        "--candidate-dir",
        type=Path,
        default=ROOT / "models" / "candidates" / "for_norm_stream_flush_seed42_20261020",
    )
    parser.add_argument("--training-manifest", type=Path, default=None)
    parser.add_argument(
        "--output",
        type=Path,
        default=ROOT
        / "results"
        / "candidates"
        / "for_rerec_external_stream_seed42_20261021.json",
    )
    parser.add_argument(
        "--test-split-previously-screened",
        action="store_true",
        help="record that this test split influenced earlier candidate diagnostics",
    )
    parser.add_argument("--supersedes-report", type=Path, default=None)
    return parser.parse_args()


def read_manifest(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as stream:
        return list(csv.DictReader(stream))


def overlap_audit(
    evaluation_rows: list[dict[str, str]], training_rows: list[dict[str, str]]
) -> dict[str, int]:
    external_hashes = {row.get("sha256", "").casefold() for row in evaluation_rows}
    training_hashes = {row.get("sha256", "").casefold() for row in training_rows}
    external_names = {Path(row["path"]).name.casefold() for row in evaluation_rows}
    training_names = {Path(row["path"]).name.casefold() for row in training_rows}
    external_hashes.discard("")
    training_hashes.discard("")
    return {
        "exact_sha256_intersections": len(external_hashes & training_hashes),
        "basename_intersections": len(external_names & training_names),
        "evaluation_rows_with_speaker_ids": sum(bool(row.get("speaker")) for row in evaluation_rows),
        "evaluation_rows_with_generator_ids": sum(bool(row.get("generator")) for row in evaluation_rows),
    }


def class_counts(rows: list[dict[str, str]]) -> dict[str, int]:
    return dict(sorted(Counter(row["label"] for row in rows).items()))


def main() -> None:
    args = parse_args()
    report_path = args.output.resolve()
    if report_path.exists():
        raise FileExistsError(f"Refusing to overwrite report: {report_path}")

    rows = [
        row
        for row in read_manifest(args.manifest)
        if row.get("split") == "testing" and row.get("label") in {"0", "1"}
    ]
    if not rows:
        raise ValueError(f"No labeled testing rows found in {args.manifest}")

    meta_path = args.candidate_dir / "model_meta.json"
    meta: dict[str, Any] = json.loads(meta_path.read_text(encoding="utf-8"))
    candidate_manifest = args.training_manifest or Path(
        meta["training_protocol"]["manifest"]
    )
    training_rows = [
        row
        for row in read_manifest(candidate_manifest)
        if row.get("split") == "training" and row.get("label") in {"0", "1"}
    ]
    overlap = overlap_audit(rows, training_rows)
    if overlap["exact_sha256_intersections"] or overlap["basename_intersections"]:
        raise ValueError(f"Evaluation split overlaps the candidate training manifest: {overlap}")

    model_path = args.candidate_dir / str(meta["model_path"])
    sample_rate = int(meta["sample_rate"])
    mfcc = MFCCConfig(sample_rate=sample_rate, **meta["mfcc"])
    active = Detector()
    if sample_rate != active.sample_rate or float(meta["window_seconds"]) != active.window_seconds:
        raise ValueError("Candidate preprocessing does not match the active stream window")

    candidate = ModelWindowScorer(
        joblib.load(model_path),
        mfcc,
        float(meta["threshold"]),
        active.config.uncertain_band,
    )
    metrics = evaluate_test_stream(rows, candidate, active)
    same_dataset_source = Path(args.manifest).resolve() == Path(candidate_manifest).resolve()
    report = {
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "experiment": "frozen_stream_candidate_split_evaluation",
        "evaluation_scope": (
            "same_source_manifest_test_partition"
            if same_dataset_source
            else "external_recording_condition_test"
        ),
        "manifest": str(args.manifest.resolve()),
        "split": "testing",
        "candidate_name": meta["name"],
        "candidate_training_dataset": meta["training_dataset"],
        "candidate_training_manifest": str(Path(candidate_manifest).resolve()),
        "candidate_threshold": float(meta["threshold"]),
        "threshold_source": meta["threshold_source"],
        "test_split_used_for_selection": False,
        "test_split_previously_screened_during_development": args.test_split_previously_screened,
        "supersedes_report": (
            str(args.supersedes_report.resolve()) if args.supersedes_report else None
        ),
        "evaluation_files_by_label": class_counts(rows),
        "training_partition_overlap_audit": overlap,
        "same_manifest_source": same_dataset_source,
        "stream_window_seconds": candidate.window_seconds,
        "stream_hop_seconds": 1.0,
        "metrics": metrics,
        "interpretation_limits": [
            "The candidate C value and threshold were selected on its validation split; this test split was not used for selection.",
            "The source manifest has no speaker or generator identifiers; speaker or source-content overlap cannot be ruled out.",
            "The test split was previously screened during development; treat this score as diagnostic rather than fresh independent confirmation."
            if args.test_split_previously_screened
            else "No per-speaker or per-generator generalization claim is possible without those IDs.",
            "The candidate remains inactive and these scores are not calibrated real-world probabilities.",
        ],
    }
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2))
    print(f"saved_report={report_path}")


if __name__ == "__main__":
    main()

"""Replay a labeled manifest split through the same windowed stream pipeline as /ws/live."""

from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path
from time import perf_counter
from typing import Any

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.core.audio_utils import decode_audio_file
from app.core.asvspoof_detector import ASVspoofDetector
from app.core.detector import Detector, DetectorConfig
from app.core.streaming import StreamSession
from src.svf.eval.metrics import classification_metrics


ROOT = Path(__file__).resolve().parents[1]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, default=ROOT / "data" / "manifests" / "for_2sec.csv")
    parser.add_argument("--split", choices=("validation", "testing"), default="validation")
    parser.add_argument("--max-files-per-class", type=int, default=50)
    parser.add_argument("--frame-samples", type=int, default=4096)
    parser.add_argument("--min-duration", type=float, default=0.0)
    parser.add_argument("--demo-manifest", type=Path, default=ROOT / "data" / "manifests" / "asvspoof_la_demo_holdout.csv")
    return parser.parse_args()


def select_rows(manifest: Path, split: str, per_class: int, min_duration: float) -> list[dict[str, str]]:
    if per_class < 1:
        raise ValueError("max-files-per-class must be positive")
    counts = {"0": 0, "1": 0}
    selected: list[dict[str, str]] = []
    with manifest.open(newline="", encoding="utf-8") as stream:
        for row in csv.DictReader(stream):
            if row.get("split") != split or row.get("label") not in counts:
                continue
            duration_text = row.get("duration_seconds") or row.get("duration_s")
            if duration_text is not None and float(duration_text) < min_duration:
                continue
            label = row["label"]
            if counts[label] == per_class:
                continue
            selected.append(row)
            counts[label] += 1
            if all(count == per_class for count in counts.values()):
                break
    if any(count != per_class for count in counts.values()):
        raise ValueError(f"{manifest} has insufficient {split} rows: {counts}")
    return selected


def replay_file(
    detector: Detector, row: dict[str, str], frame_samples: int
) -> tuple[dict[str, Any], list[dict[str, Any]], float, bool]:
    audio, sample_rate = decode_audio_file(row["path"], detector.sample_rate)
    session = StreamSession(
        detector=detector,
        sample_rate=detector.sample_rate,
        mode="evaluation",
        source="manifest",
    )
    events: list[dict[str, Any]] = []
    started = perf_counter()
    for offset in range(0, audio.size, frame_samples):
        events.extend(session.add_frame(audio[offset : offset + frame_samples]))
    elapsed_ms = (perf_counter() - started) * 1000.0
    return (
        session.summary(),
        [event for event in events if event["type"] == "window"],
        elapsed_ms,
        any(event["type"] == "alert" for event in events),
    )


def evaluate(rows: list[dict[str, str]], frame_samples: int) -> dict[str, Any]:
    if frame_samples < 1:
        raise ValueError("frame-samples must be positive")
    detector = Detector(config=DetectorConfig())
    window_labels: list[int] = []
    window_scores: list[float] = []
    window_latencies: list[float] = []
    file_labels: list[int] = []
    file_scores: list[float] = []
    file_latencies: list[float] = []
    alert_counts: dict[str, int] = {"real": 0, "fake": 0}
    no_speech_files = 0
    for row in rows:
        label = int(row["label"])
        summary, windows, total_ms, alerted = replay_file(detector, row, frame_samples)
        if summary["mean_prob"] is None:
            no_speech_files += 1
        else:
            file_labels.append(label)
            file_scores.append(float(summary["mean_prob"]))
            file_latencies.append(total_ms)
        scored = [window for window in windows if window["speech"] and window["prob"] is not None]
        window_labels.extend([label] * len(scored))
        window_scores.extend(float(window["smoothed"]) for window in scored)
        window_latencies.extend(float(window["latency_ms"]) for window in scored)
        alert_counts["fake" if label else "real"] += int(alerted)

    threshold = detector.threshold
    return {
        "model_version": detector.meta["model_version"],
        "manifest_split": rows[0]["split"] if rows else None,
        "duration_filter_s": None,
        "threshold_source": detector.meta["threshold_source"],
        "threshold": threshold,
        "files_requested": len(rows),
        "files_scored": len(file_scores),
        "files_no_speech": no_speech_files,
        "window_level": classification_metrics(np.asarray(window_labels), np.asarray(window_scores), threshold),
        "file_level": classification_metrics(np.asarray(file_labels), np.asarray(file_scores), threshold),
        "latency_ms": {
            "window_mean": float(np.mean(window_latencies)) if window_latencies else None,
            "window_median": float(np.median(window_latencies)) if window_latencies else None,
            "window_p95": float(np.percentile(window_latencies, 95)) if window_latencies else None,
            "file_mean": float(np.mean(file_latencies)) if file_latencies else None,
            "file_median": float(np.median(file_latencies)) if file_latencies else None,
            "file_p95": float(np.percentile(file_latencies, 95)) if file_latencies else None,
        },
        "alerted_files_by_ground_truth": alert_counts,
        "limitation": "The ASVspoof demo holdout is reported separately below with its matching complete-clip model; it is not scored through the FoR WebSocket model.",
    }


def evaluate_demo_holdout(manifest: Path) -> dict[str, Any]:
    """Evaluate the locked demo separately with its matching complete-clip model."""
    detector = ASVspoofDetector()
    labels: list[int] = []
    scores: list[float] = []
    latencies: list[float] = []
    with manifest.open(newline="", encoding="utf-8") as stream:
        rows = list(csv.DictReader(stream))
    for row in rows:
        audio, sample_rate = decode_audio_file(row["path"], detector.sample_rate)
        started = perf_counter()
        result = detector.analyze_array(audio, sample_rate)
        latencies.append((perf_counter() - started) * 1000.0)
        if result["mean_prob"] is None:
            continue
        labels.append(int(row["label"]))
        scores.append(float(result["mean_prob"]))
    if not labels or len(set(labels)) != 2:
        raise ValueError("demo holdout must contain scored samples from both classes")
    return {
        "model_version": detector.meta["model_version"],
        "inference_kind": "complete_clip; not the WebSocket streaming detector",
        "files_requested": len(rows),
        "files_scored": len(scores),
        "metrics": classification_metrics(np.asarray(labels), np.asarray(scores), detector.threshold),
        "latency_ms": {
            "mean": float(np.mean(latencies)),
            "median": float(np.median(latencies)),
            "p95": float(np.percentile(latencies, 95)),
        },
        "threshold_source": detector.meta["threshold_source"],
        "threshold": detector.threshold,
        "note": "Locked demo_holdout evaluated separately for demonstration evidence; not used to fit or tune the model or threshold.",
    }


def main() -> None:
    args = parse_args()
    if args.frame_samples < 1:
        raise SystemExit("--frame-samples must be positive")
    if args.min_duration < 0.0:
        raise SystemExit("--min-duration cannot be negative")
    rows = select_rows(args.manifest, args.split, args.max_files_per_class, args.min_duration)
    report = evaluate(rows, args.frame_samples)
    report["duration_filter_s"] = args.min_duration
    report["manifest"] = str(args.manifest.resolve())
    report["demo_holdout_separate_clip_evaluation"] = evaluate_demo_holdout(args.demo_manifest)
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()

"""Measure end-to-end latency for load, preprocess, MFCC extraction, and prediction."""

from __future__ import annotations

import argparse
import csv
import json
import statistics
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import joblib
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.svf.audio_io import AudioConfig, load_audio
from src.svf.features.mfcc import MFCCConfig, extract_mfcc, summarize_mfcc


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--model", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--max-files", type=int, default=20)
    parser.add_argument("--repeats", type=int, default=3)
    return parser.parse_args()


def percentile(values: list[float], fraction: float) -> float:
    return sorted(values)[min(len(values) - 1, round((len(values) - 1) * fraction))]


def main() -> None:
    args = parse_args()
    model = joblib.load(args.model)
    paths: list[tuple[str, int]] = []
    with args.manifest.open(newline="", encoding="utf-8") as stream:
        for row in csv.DictReader(stream):
            if row["split"] == "testing":
                paths.append((row["path"], int(row["sample_rate"])))
            if len(paths) >= args.max_files:
                break
    timings_ms: list[float] = []
    audio_durations: list[float] = []
    for path, sample_rate in paths:
        for _ in range(args.repeats):
            started = time.perf_counter()
            audio, actual_rate = load_audio(path, AudioConfig(sample_rate=sample_rate))
            vector = summarize_mfcc(extract_mfcc(audio, MFCCConfig(sample_rate=actual_rate))).reshape(1, -1)
            model.predict_proba(vector)
            elapsed_ms = (time.perf_counter() - started) * 1000.0
            timings_ms.append(elapsed_ms)
            audio_durations.append(audio.size / actual_rate)
    report = {
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "experiment": "end_to_end_latency",
        "manifest": str(args.manifest.resolve()),
        "model": str(args.model.resolve()),
        "files": len(paths),
        "repeats": args.repeats,
        "audio_duration_seconds": statistics.fmean(audio_durations),
        "latency_ms": {
            "count": len(timings_ms),
            "mean": statistics.fmean(timings_ms),
            "median": statistics.median(timings_ms),
            "p95": percentile(timings_ms, 0.95),
            "min": min(timings_ms),
            "max": max(timings_ms),
        },
        "hardware_note": "CPU measurement; exact processor and RAM not yet recorded",
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2))
    print(f"Saved latency report: {args.output}")


if __name__ == "__main__":
    main()
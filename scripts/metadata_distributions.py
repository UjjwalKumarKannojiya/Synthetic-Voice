"""Summarize metadata distributions by split and label from a manifest."""

from __future__ import annotations

import argparse
import csv
import json
import statistics
import sys
from collections import defaultdict
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.svf.audio_io import AudioConfig, load_audio


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--silence-threshold", type=float, default=0.01)
    return parser.parse_args()


def summarize(values: list[float]) -> dict[str, float | int | None]:
    if not values:
        return {"count": 0, "min": None, "mean": None, "median": None, "max": None}
    return {
        "count": len(values),
        "min": min(values),
        "mean": statistics.fmean(values),
        "median": statistics.median(values),
        "max": max(values),
    }


def main() -> None:
    args = parse_args()
    grouped: defaultdict[tuple[str, int], dict[str, list[float]]] = defaultdict(
        lambda: {"duration_seconds": [], "sample_rate": [], "channels": [], "file_size_bytes": [], "rms": [], "silence_ratio": []}
    )
    with args.manifest.open(newline="", encoding="utf-8") as stream:
        for row in csv.DictReader(stream):
            key = (row["split"], int(row["label"]))
            audio, _ = load_audio(row["path"], AudioConfig(sample_rate=int(row["sample_rate"])))
            grouped[key]["duration_seconds"].append(float(row["duration_seconds"]))
            grouped[key]["sample_rate"].append(float(row["sample_rate"]))
            grouped[key]["channels"].append(float(row["channels"]))
            grouped[key]["file_size_bytes"].append(float(row["file_size_bytes"]))
            grouped[key]["rms"].append(float(np.sqrt(np.mean(np.square(audio), dtype=np.float64))))
            grouped[key]["silence_ratio"].append(float(np.mean(np.abs(audio) <= args.silence_threshold)))

    report = {
        f"{split}/label_{label}": {name: summarize(values) for name, values in features.items()}
        for (split, label), features in sorted(grouped.items())
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2))
    print(f"Saved distributions: {args.output}")


if __name__ == "__main__":
    main()
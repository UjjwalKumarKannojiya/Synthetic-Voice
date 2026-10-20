"""Discover and summarize an audio dataset without loading all audio into memory."""

from __future__ import annotations

import argparse
import json
import platform
import statistics
import sys
import wave
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

AUDIO_EXTENSIONS = {".wav", ".flac", ".ogg", ".mp3", ".m4a", ".aac"}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-path", type=Path, required=True)
    parser.add_argument("--output", type=Path, default=Path("results/data_audit.json"))
    return parser.parse_args()


def percentile(values: list[float], fraction: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    index = min(len(ordered) - 1, round((len(ordered) - 1) * fraction))
    return ordered[index]


def summarize(values: list[float]) -> dict[str, float | int | None]:
    return {
        "count": len(values),
        "min": min(values) if values else None,
        "mean": statistics.fmean(values) if values else None,
        "median": statistics.median(values) if values else None,
        "p95": percentile(values, 0.95),
        "max": max(values) if values else None,
    }


def inspect_audio(path: Path) -> dict[str, Any]:
    try:
        if path.suffix.lower() != ".wav":
            return {
                "status": "unsupported_without_optional_reader",
                "error": "Stage 0 standard-library audit supports WAV files only",
            }
        with wave.open(str(path), "rb") as audio:
            sample_rate = audio.getframerate()
            channels_count = audio.getnchannels()
            frames = audio.getnframes()
            sample_width = audio.getsampwidth()
        return {
            "status": "ok",
            "sample_rate": sample_rate,
            "channels": channels_count,
            "frames": frames,
            "duration_seconds": frames / sample_rate if sample_rate else None,
            "format": "WAV",
            "subtype": f"PCM_{sample_width * 8}",
        }
    except Exception as error:  # noqa: BLE001 - audit must record bad files and continue.
        return {"status": "error", "error": f"{type(error).__name__}: {error}"}


def audit(data_path: Path) -> dict[str, Any]:
    if not data_path.is_dir():
        raise SystemExit(f"Dataset directory does not exist: {data_path}")

    files = sorted(
        path for path in data_path.rglob("*") if path.is_file() and path.suffix.lower() in AUDIO_EXTENSIONS
    )
    split_counts: Counter[str] = Counter()
    label_counts: Counter[str] = Counter()
    split_label_counts: Counter[str] = Counter()
    sample_rates: list[float] = []
    durations: list[float] = []
    channels: Counter[str] = Counter()
    formats: Counter[str] = Counter()
    errors: list[dict[str, str]] = []
    unknown_path_parts: Counter[str] = Counter()

    for path in files:
        relative_parts = path.relative_to(data_path).parts
        split = next((part for part in relative_parts if part.lower() in {"training", "validation", "testing"}), "unknown")
        label = next((part.lower() for part in relative_parts if part.lower() in {"real", "fake", "bona_fide", "spoof"}), "unknown")
        split_counts[split] += 1
        label_counts[label] += 1
        split_label_counts[f"{split}/{label}"] += 1
        if split == "unknown" or label == "unknown":
            unknown_path_parts[str(path)] += 1

        metadata = inspect_audio(path)
        if metadata["status"] == "error":
            errors.append({"path": str(path), "error": metadata["error"]})
            continue
        sample_rates.append(float(metadata["sample_rate"]))
        durations.append(float(metadata["duration_seconds"]))
        channels[str(metadata["channels"])] += 1
        formats[str(metadata["format"])] += 1

    return {
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "dataset_path": str(data_path.resolve()),
        "python": sys.version,
        "platform": platform.platform(),
        "audio_extensions": sorted(AUDIO_EXTENSIONS),
        "file_count": len(files),
        "split_counts": dict(sorted(split_counts.items())),
        "label_counts": dict(sorted(label_counts.items())),
        "split_label_counts": dict(sorted(split_label_counts.items())),
        "sample_rate_hz": summarize(sample_rates),
        "duration_seconds": summarize(durations),
        "channels": dict(sorted(channels.items())),
        "formats": dict(sorted(formats.items())),
        "read_errors": errors,
        "unknown_split_or_label_paths": sorted(unknown_path_parts),
        "speaker_information": "not inferred by this audit; inspect metadata or naming rules before splitting",
        "generator_information": "not inferred by this audit; inspect metadata or naming rules before unseen-generator claims",
    }


def main() -> None:
    args = parse_args()
    report = audit(args.data_path)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(f"Dataset: {report['dataset_path']}")
    print(f"Audio files: {report['file_count']}")
    print(f"Splits: {report['split_counts']}")
    print(f"Labels: {report['label_counts']}")
    print(f"Split/label counts: {report['split_label_counts']}")
    print(f"Read errors: {len(report['read_errors'])}")
    print(f"Saved audit: {args.output}")


if __name__ == "__main__":
    main()
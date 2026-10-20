"""Build a CSV manifest from an audited folder-based audio dataset."""

from __future__ import annotations

import argparse
import csv
import hashlib
import sys
import wave
from collections import Counter
from pathlib import Path


AUDIO_EXTENSIONS = {".wav", ".flac", ".ogg", ".mp3", ".m4a", ".aac"}
SPLITS = {"training", "validation", "testing"}
LABELS = {"real": 0, "bona_fide": 0, "fake": 1, "spoof": 1}
FIELDS = [
    "path",
    "dataset_variant",
    "label",
    "split",
    "speaker",
    "generator",
    "duration_seconds",
    "sample_rate",
    "channels",
    "file_size_bytes",
    "sha256",
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-path", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--dataset-variant", required=True)
    parser.add_argument(
        "--exclude-path",
        action="append",
        default=[],
        type=Path,
        help="Path to exclude from the manifest; may be supplied more than once",
    )
    return parser.parse_args()


def sha256_file(path: Path, chunk_size: int = 1024 * 1024) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        while chunk := stream.read(chunk_size):
            digest.update(chunk)
    return digest.hexdigest()


def wav_metadata(path: Path) -> tuple[float, int, int]:
    with wave.open(str(path), "rb") as audio:
        sample_rate = audio.getframerate()
        channels = audio.getnchannels()
        frames = audio.getnframes()
    if sample_rate <= 0:
        raise ValueError("sample rate must be positive")
    return frames / sample_rate, sample_rate, channels


def metadata(path: Path) -> tuple[float, int, int]:
    if path.suffix.lower() != ".wav":
        raise ValueError("manifest currently supports WAV files only")
    return wav_metadata(path)


def discover_rows(
    data_path: Path, variant: str, excluded_paths: set[Path] | None = None
) -> list[dict[str, str | int | float]]:
    if not data_path.is_dir():
        raise SystemExit(f"Dataset directory does not exist: {data_path}")

    excluded_paths = {path.resolve() for path in (excluded_paths or set())}
    rows: list[dict[str, str | int | float]] = []
    seen_paths: set[str] = set()
    seen_hashes: dict[str, str] = {}
    split_counts: Counter[str] = Counter()
    label_counts: Counter[int] = Counter()

    for path in sorted(data_path.rglob("*")):
        if not path.is_file() or path.suffix.lower() not in AUDIO_EXTENSIONS:
            continue
        if path.resolve() in excluded_paths:
            continue
        relative_parts = path.relative_to(data_path).parts
        split = next((part.lower() for part in relative_parts if part.lower() in SPLITS), None)
        label_name = next((part.lower() for part in relative_parts if part.lower() in LABELS), None)
        if split is None or label_name is None:
            raise ValueError(f"Could not infer split and label from path: {path}")

        absolute_path = str(path.resolve())
        if absolute_path in seen_paths:
            raise ValueError(f"Duplicate path: {absolute_path}")
        seen_paths.add(absolute_path)

        file_hash = sha256_file(path)
        previous_path = seen_hashes.get(file_hash)
        if previous_path is not None:
            raise ValueError(f"Duplicate file content: {path} matches {previous_path}")
        seen_hashes[file_hash] = absolute_path

        duration, sample_rate, channels = metadata(path)
        label = LABELS[label_name]
        split_counts[split] += 1
        label_counts[label] += 1
        rows.append(
            {
                "path": absolute_path,
                "dataset_variant": variant,
                "label": label,
                "split": split,
                "speaker": "",
                "generator": "",
                "duration_seconds": duration,
                "sample_rate": sample_rate,
                "channels": channels,
                "file_size_bytes": path.stat().st_size,
                "sha256": file_hash,
            }
        )

    if not rows:
        raise SystemExit(f"No supported audio files found under {data_path}")
    if set(split_counts) != SPLITS:
        raise ValueError(f"Expected training, validation, and testing splits; found {dict(split_counts)}")
    print(f"Manifest rows: {len(rows)}")
    print(f"Split counts: {dict(sorted(split_counts.items()))}")
    print(f"Label counts: {dict(sorted(label_counts.items()))}")
    return rows


def main() -> None:
    args = parse_args()
    rows = discover_rows(args.data_path, args.dataset_variant, set(args.exclude_path))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=FIELDS)
        writer.writeheader()
        writer.writerows(rows)
    print(f"Saved manifest: {args.output}")


if __name__ == "__main__":
    main()
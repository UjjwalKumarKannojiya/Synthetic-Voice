"""Stream a manifest and cache fixed-shape log-mel spectrograms."""

from __future__ import annotations

import argparse
import csv
import sys
from collections import Counter
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.svf.audio_io import AudioConfig, load_audio
from src.svf.features.spectrogram import SpectrogramConfig, extract_log_mel


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--max-files-per-class", type=int, default=None)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=True)
    index_path = args.output_dir / "index.csv"
    counts: Counter[tuple[str, int]] = Counter()
    processed = 0
    skipped = 0
    with args.manifest.open(newline="", encoding="utf-8") as manifest_stream, index_path.open(
        "w", newline="", encoding="utf-8"
    ) as index_stream:
        reader = csv.DictReader(manifest_stream)
        fields = ["feature_path", "source_path", "dataset_variant", "label", "split", "feature_shape"]
        writer = csv.DictWriter(index_stream, fieldnames=fields)
        writer.writeheader()
        for row in reader:
            key = (row["split"], int(row["label"]))
            if args.max_files_per_class is not None and counts[key] >= args.max_files_per_class:
                skipped += 1
                continue
            audio, sample_rate = load_audio(row["path"], AudioConfig(sample_rate=int(row["sample_rate"])))
            image = extract_log_mel(audio, SpectrogramConfig(sample_rate=sample_rate))
            feature_path = args.output_dir / f"{row['sha256']}.npy"
            np.save(feature_path, image.astype(np.float32, copy=False), allow_pickle=False)
            writer.writerow(
                {
                    "feature_path": str(feature_path.resolve()),
                    "source_path": row["path"],
                    "dataset_variant": row["dataset_variant"],
                    "label": row["label"],
                    "split": row["split"],
                    "feature_shape": "64,200",
                }
            )
            counts[key] += 1
            processed += 1
    print(f"Cached spectrograms: {processed}")
    print(f"Skipped by subset limit: {skipped}")
    print("Feature shape: (64, 200)")
    print(f"Saved feature index: {index_path}")


if __name__ == "__main__":
    main()
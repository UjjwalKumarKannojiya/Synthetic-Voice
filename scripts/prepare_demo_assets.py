"""Prepare a small, attributed ASVspoof development-split replay set locally."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import shutil
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_MANIFEST = ROOT / "data" / "manifests" / "asvspoof_la_val.csv"
DEFAULT_OUTPUT = ROOT / ".local-notes" / "demo-assets-r9"
FIELDS = ("path", "label", "split", "speaker", "attack_id", "sr", "duration_s", "sha1")
NOTICE = """# VoiceGuard Demo Replay audio attribution

This small replay set contains unchanged audio clips selected from the ASVspoof 2019
Logical Access development partition. It is a demonstration subset, not a benchmark.
The ASVspoof development partition was also used for model threshold selection, so
these examples do not provide independent accuracy evidence. The locked evaluation
demo holdout is not included.

Database: ASVspoof 2019, University of Edinburgh, Centre for Speech Technology
Research (CSTR), https://doi.org/10.7488/ds/2555. The database is made available
under the Open Data Commons Attribution License (ODC-By) 1.0:
https://opendatacommons.org/licenses/by/1-0/ .

Underlying source speech: CSTR VCTK Corpus v0.92, University of Edinburgh,
https://doi.org/10.7488/ds/2645, licensed under Creative Commons Attribution 4.0:
https://creativecommons.org/licenses/by/4.0/ .

Adaptation: eight clips (four bona fide and four spoofed) were selected from the
development partition and copied without audio modification for authenticated
in-app replay. Labels are hidden until analysis completes. Detector scores are
estimates, not proof, and this subset must not be used to claim model accuracy.
"""


def _sha1(path: Path) -> str:
    digest = hashlib.sha1()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _rank(seed: int, sample_id: str) -> str:
    return hashlib.sha256(f"{seed}:{sample_id}".encode("ascii")).hexdigest()


def _select(rows: list[dict[str, str]], per_class: int, seed: int) -> list[dict[str, str]]:
    if per_class < 2 or per_class > 6:
        raise ValueError("Demo set size must be from 2 to 6 files per class")
    eligible = [row for row in rows if row.get("split") == "val" and row.get("label") in {"0", "1"}]
    if not eligible:
        raise ValueError("No validation-split rows are available for the demo")

    selected: list[dict[str, str]] = []
    used_speakers: set[str] = set()
    for label in ("0", "1"):
        candidates = sorted(
            (row for row in eligible if row["label"] == label),
            key=lambda row: _rank(seed, row["sha1"]),
        )
        class_rows: list[dict[str, str]] = []
        class_speakers: set[str] = set()
        for row in candidates:
            speaker = row.get("speaker", "")
            if not speaker or speaker in used_speakers or speaker in class_speakers:
                continue
            class_rows.append(row)
            class_speakers.add(speaker)
            if len(class_rows) == per_class:
                break
        if len(class_rows) != per_class:
            raise ValueError(f"Could not select {per_class} speaker-distinct clips for label {label}")
        used_speakers.update(class_speakers)
        selected.extend(class_rows)

    attacks = {row.get("attack_id") for row in selected if row["label"] == "1"}
    if len(attacks) < 2:
        raise ValueError("Selected spoof examples do not cover at least two attack systems")
    return selected


def prepare(
    source_manifest: Path,
    output_dir: Path,
    *,
    dataset_root: Path,
    per_class: int = 4,
    seed: int = 42,
) -> dict[str, Any]:
    source_manifest = source_manifest.resolve()
    output_dir = output_dir.resolve()
    dataset_root = dataset_root.resolve()
    if output_dir.exists():
        raise FileExistsError(f"Refusing to overwrite existing demo assets: {output_dir}")
    with source_manifest.open(encoding="utf-8", newline="") as stream:
        reader = csv.DictReader(stream)
        if not reader.fieldnames or not set(FIELDS).issubset(reader.fieldnames):
            raise ValueError("Source manifest does not have the ASVspoof manifest fields")
        rows = list(reader)

    selected = _select(rows, per_class, seed)
    output_dir.mkdir(parents=True)
    audio_dir = output_dir / "audio"
    audio_dir.mkdir()
    output_rows: list[dict[str, str]] = []
    total_bytes = 0
    for row in selected:
        source = Path(row["path"]).resolve()
        if not source.is_relative_to(dataset_root) or source.suffix.lower() != ".flac" or not source.is_file():
            raise ValueError("A selected audio path is missing or outside the local ASVspoof dataset")
        if row["split"] != "val" or _sha1(source) != row["sha1"]:
            raise ValueError("A selected audio file failed validation-manifest checks")
        name = f"{row['sha1']}.flac"
        shutil.copyfile(source, audio_dir / name)
        total_bytes += source.stat().st_size
        output_row = {field: row[field] for field in FIELDS}
        output_row["path"] = f"audio/{name}"
        output_row["name"] = source.name
        output_rows.append(output_row)

    fields = (*FIELDS, "name")
    with (output_dir / "manifest.csv").open("x", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        writer.writerows(output_rows)
    (output_dir / "NOTICE.md").write_text(NOTICE, encoding="utf-8", newline="\n")
    return {
        "output": str(output_dir),
        "sample_count": len(output_rows),
        "class_counts": {label: sum(row["label"] == label for row in output_rows) for label in ("0", "1")},
        "speaker_count": len({row["speaker"] for row in output_rows}),
        "spoof_attack_ids": sorted({row["attack_id"] for row in output_rows if row["label"] == "1"}),
        "source_split": "val",
        "locked_demo_holdout_used": False,
        "audio_bytes": total_bytes,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--dataset-root", type=Path, default=ROOT / "LA")
    parser.add_argument("--per-class", type=int, default=4)
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()
    local_only = (ROOT / ".local-notes").resolve()
    output = args.output.resolve()
    if not output.is_relative_to(local_only):
        raise ValueError("Demo assets must be written under the ignored .local-notes directory")
    print(json.dumps(prepare(args.manifest, output, dataset_root=args.dataset_root, per_class=args.per_class, seed=args.seed), indent=2))


if __name__ == "__main__":
    main()

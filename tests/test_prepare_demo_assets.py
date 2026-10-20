from __future__ import annotations

import csv
import hashlib
from pathlib import Path

import pytest

from scripts.prepare_demo_assets import prepare


def _source_manifest(tmp_path: Path) -> tuple[Path, Path, dict[str, bytes]]:
    dataset_root = tmp_path / "dataset"
    audio_root = dataset_root / "dev" / "flac"
    audio_root.mkdir(parents=True)
    manifest = tmp_path / "validation.csv"
    payloads: dict[str, bytes] = {}
    rows = []
    for index, label in enumerate(("0", "0", "1", "1")):
        payload = f"fixture-audio-{index}".encode()
        sample_id = hashlib.sha1(payload).hexdigest()
        name = f"LA_D_fixture{index}.flac"
        path = audio_root / name
        path.write_bytes(payload)
        payloads[name] = payload
        rows.append({
            "path": str(path),
            "label": label,
            "split": "val",
            "speaker": f"speaker-{index}",
            "attack_id": ("-" if label == "0" else f"A0{index}"),
            "sr": "16000",
            "duration_s": "2.0",
            "sha1": sample_id,
        })
    with manifest.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=rows[0].keys())
        writer.writeheader()
        writer.writerows(rows)
    return manifest, dataset_root, payloads


def test_prepare_copies_balanced_validation_audio_without_overwriting(tmp_path: Path) -> None:
    manifest, dataset_root, payloads = _source_manifest(tmp_path)
    output = tmp_path / "demo-assets"

    result = prepare(manifest, output, dataset_root=dataset_root, per_class=2, seed=19)

    assert result["sample_count"] == 4
    assert result["class_counts"] == {"0": 2, "1": 2}
    assert result["speaker_count"] == 4
    assert result["source_split"] == "val"
    assert result["locked_demo_holdout_used"] is False
    with (output / "manifest.csv").open(encoding="utf-8", newline="") as stream:
        rows = list(csv.DictReader(stream))
    assert len({row["speaker"] for row in rows}) == 4
    assert len({row["attack_id"] for row in rows if row["label"] == "1"}) == 2
    for row in rows:
        assert row["path"].startswith("audio/")
        assert (output / row["path"]).read_bytes() == payloads[row["name"]]
    assert "ODC-By" in (output / "NOTICE.md").read_text(encoding="utf-8")
    with pytest.raises(FileExistsError, match="Refusing to overwrite"):
        prepare(manifest, output, dataset_root=dataset_root, per_class=2, seed=19)


def test_prepare_rejects_locked_or_non_validation_rows(tmp_path: Path) -> None:
    manifest, dataset_root, _ = _source_manifest(tmp_path)
    with manifest.open(encoding="utf-8", newline="") as stream:
        reader = csv.DictReader(stream)
        rows = list(reader)
        fields = reader.fieldnames
    assert fields
    for row in rows:
        row["split"] = "test"
    with manifest.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)

    with pytest.raises(ValueError, match="No validation-split rows"):
        prepare(manifest, tmp_path / "blocked", dataset_root=dataset_root, per_class=2)

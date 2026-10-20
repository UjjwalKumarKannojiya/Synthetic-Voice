"""Leakage checks for the ASVspoof LA four-way manifests."""

from __future__ import annotations

import csv
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MANIFESTS = ROOT / "data" / "manifests"
NAMES = {
    "train": "asvspoof_la_train.csv",
    "val": "asvspoof_la_val.csv",
    "test": "asvspoof_la_test.csv",
    "demo_holdout": "asvspoof_la_demo_holdout.csv",
}


def load(name: str) -> list[dict[str, str]]:
    path = MANIFESTS / NAMES[name]
    if not path.exists():
        raise AssertionError(f"missing manifest: {path}")
    with path.open(encoding="utf-8", newline="") as stream:
        return list(csv.DictReader(stream))


def test_four_sets_have_no_path_hash_or_speaker_overlap() -> None:
    sets = {name: load(name) for name in NAMES}
    for left_name, left_rows in sets.items():
        for right_name, right_rows in sets.items():
            if left_name >= right_name:
                continue
            for field in ("path", "sha1", "speaker"):
                left = {row[field] for row in left_rows}
                right = {row[field] for row in right_rows}
                assert not left & right, f"{field} overlap: {left_name} vs {right_name}"


def test_manifest_schema_and_labels() -> None:
    for name in NAMES:
        rows = load(name)
        assert rows
        assert set(rows[0]) == {"path", "label", "split", "speaker", "attack_id", "sr", "duration_s", "sha1"}
        assert {row["label"] for row in rows} <= {"0", "1"}
        assert all(Path(row["path"]).is_file() for row in rows[:10])


def test_demo_holdout_is_balanced_and_not_training_data() -> None:
    rows = load("demo_holdout")
    assert sum(row["label"] == "0" for row in rows) == 25
    assert sum(row["label"] == "1" for row in rows) == 25
    assert len({row["speaker"] for row in rows}) >= 1
    assert len({row["attack_id"] for row in rows if row["label"] == "1"}) >= 2

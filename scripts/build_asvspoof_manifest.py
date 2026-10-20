"""Build leakage-safe ASVspoof 2019 LA manifests from CM protocols."""

from __future__ import annotations

import argparse
import csv
import hashlib
import random
import sys
from collections import Counter, defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from itertools import combinations
from pathlib import Path

import soundfile as sf


PARTITIONS = {
    "train": ("ASVspoof2019.LA.cm.train.trn.txt", "LA_T_"),
    "val": ("ASVspoof2019.LA.cm.dev.trl.txt", "LA_D_"),
    "eval": ("ASVspoof2019.LA.cm.eval.trl.txt", "LA_E_"),
}
FIELDS = ["path", "label", "split", "speaker", "attack_id", "sr", "duration_s", "sha1"]


def parse_protocol(path: Path) -> dict[str, tuple[str, int, str]]:
    records: dict[str, tuple[str, int, str]] = {}
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        fields = line.split()
        if not fields:
            continue
        if len(fields) != 5:
            raise ValueError(f"{path}:{line_number}: expected 5 fields, got {len(fields)}")
        speaker, file_id, system_id, attack_id, key = fields
        if key not in {"bonafide", "spoof"}:
            raise ValueError(f"{path}:{line_number}: unknown key {key!r}")
        if file_id in records:
            raise ValueError(f"{path}:{line_number}: duplicate file ID {file_id}")
        records[file_id] = (speaker, 0 if key == "bonafide" else 1, "-" if key == "bonafide" else attack_id)
    return records


def sha1_file(path: Path) -> str:
    digest = hashlib.sha1()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def audio_row(
    item: tuple[str, tuple[str, int, str], Path, str],
) -> dict[str, object]:
    file_id, (speaker, label, attack_id), path, split = item
    info = sf.info(path)
    return {
        "path": str(path.resolve()),
        "label": label,
        "split": split,
        "speaker": speaker,
        "attack_id": attack_id,
        "sr": info.samplerate,
        "duration_s": info.duration,
        "sha1": sha1_file(path),
        "_file_id": file_id,
    }


def choose_demo_speakers(records: dict[str, tuple[str, int, str]], target: int, seed: int) -> list[str]:
    by_speaker: dict[str, list[tuple[str, int, str]]] = defaultdict(list)
    for file_id, record in records.items():
        by_speaker[record[0]].append((file_id, record[1], record[2]))
    speakers = sorted(by_speaker)
    rng = random.Random(seed)
    rng.shuffle(speakers)
    for count in range(1, len(speakers) + 1):
        candidates = []
        for selected in combinations(speakers, count):
            rows = [item for speaker in selected for item in by_speaker[speaker]]
            real = sum(label == 0 for _, label, _ in rows)
            spoof = sum(label == 1 for _, label, _ in rows)
            attacks = {attack for _, label, attack in rows if label == 1}
            if real >= target and spoof >= target and len(attacks) >= 2:
                candidates.append((selected, real, spoof, len(attacks)))
        if candidates:
            candidates.sort(key=lambda item: (item[3], item[1] + item[2]), reverse=True)
            best = candidates[rng.randrange(min(len(candidates), 20))]
            return list(best[0])
    raise ValueError("No whole-speaker eval holdout can provide the requested class balance")


def write_manifest(path: Path, rows: list[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        path.chmod(0o666)
    with path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=FIELDS)
        writer.writeheader()
        writer.writerows({field: row[field] for field in FIELDS} for row in rows)
    path.chmod(0o444)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=Path("LA/LA"))
    parser.add_argument("--output-dir", type=Path, default=Path("data/manifests"))
    parser.add_argument("--demo-files-per-class", type=int, default=25)
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()
    if args.demo_files_per_class < 10:
        raise ValueError("demo-files-per-class must be at least 10")

    parsed: dict[str, dict[str, tuple[str, int, str]]] = {}
    rows_by_split: dict[str, list[dict[str, object]]] = {}
    excluded: list[dict[str, str]] = []
    for split, (protocol_name, prefix) in PARTITIONS.items():
        records = parse_protocol(args.root / "ASVspoof2019_LA_cm_protocols" / protocol_name)
        parsed[split] = records
        audio_dir = args.root / f"ASVspoof2019_LA_{'dev' if split == 'val' else split}" / "flac"
        actual = {path.stem: path for path in audio_dir.glob("*.flac")}
        for file_id, path in sorted(actual.items()):
            if file_id not in records:
                excluded.append({"split": split, "file_id": file_id, "reason": "not referenced by CM protocol"})
        missing = sorted(set(records) - set(actual))
        if missing:
            raise FileNotFoundError(f"{split}: {len(missing)} protocol files are missing, first={missing[0]}")
        work = [
            (file_id, records[file_id], actual[file_id], split)
            for file_id in records
        ]
        print(f"metadata_hash_jobs_{split}={len(work)}", flush=True)
        rows: list[dict[str, object]] = []
        with ThreadPoolExecutor(max_workers=8) as executor:
            futures = [executor.submit(audio_row, item) for item in work]
            for index, future in enumerate(as_completed(futures), 1):
                rows.append(future.result())
                if index % 5000 == 0 or index == len(work):
                    print(f"metadata_hash_progress_{split}={index}/{len(work)}", flush=True)
        rows_by_split[split] = rows
        if split == "train":
            write_manifest(args.output_dir / "asvspoof_la_train.csv", rows)
        elif split == "val":
            write_manifest(args.output_dir / "asvspoof_la_val.csv", rows)
        print(f"partition_manifest_{split}=written rows={len(rows)}", flush=True)

    demo_speakers = choose_demo_speakers(parsed["eval"], args.demo_files_per_class, args.seed)
    rng = random.Random(args.seed)
    eval_demo = [row for row in rows_by_split["eval"] if row["speaker"] in demo_speakers]
    real = [row for row in eval_demo if row["label"] == 0]
    spoof = [row for row in eval_demo if row["label"] == 1]
    rng.shuffle(real)
    rng.shuffle(spoof)
    demo_rows = real[:args.demo_files_per_class] + spoof[:args.demo_files_per_class]
    demo_ids = {row["_file_id"] for row in demo_rows}
    demo_hashes = {row["sha1"] for row in demo_rows}
    demo_speaker_set = set(demo_speakers)
    if len(demo_rows) != args.demo_files_per_class * 2:
        raise ValueError("demo selection did not produce the requested balanced holdout")

    for split, rows in rows_by_split.items():
        if split == "eval":
            selected = [row for row in rows if row["speaker"] not in demo_speaker_set]
            output_name = "asvspoof_la_test.csv"
        elif split == "val":
            selected = rows
            output_name = "asvspoof_la_val.csv"
        else:
            selected = rows
            output_name = "asvspoof_la_train.csv"
        for row in selected:
            row.pop("_file_id", None)
        write_manifest(args.output_dir / output_name, selected)
    for row in demo_rows:
        row.pop("_file_id", None)
    write_manifest(args.output_dir / "asvspoof_la_demo_holdout.csv", demo_rows)

    exclusions_path = args.output_dir / "asvspoof_la_exclusions.csv"
    if exclusions_path.exists():
        exclusions_path.chmod(0o666)
    with exclusions_path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=["split", "file_id", "reason"])
        writer.writeheader()
        writer.writerows(excluded)
    exclusions_path.chmod(0o444)
    print(f"seed={args.seed}")
    print(f"demo_speakers={','.join(sorted(demo_speakers))}")
    print(f"demo_rows={len(demo_rows)} demo_real={len(real[:args.demo_files_per_class])} demo_spoof={len(spoof[:args.demo_files_per_class])}")
    print(f"demo_attack_ids={','.join(sorted({row['attack_id'] for row in demo_rows if row['label'] == 1}))}")
    print(f"demo_hashes={len(demo_hashes)}")
    print(f"excluded_unreferenced={len(excluded)}")
    for name in ("asvspoof_la_train.csv", "asvspoof_la_val.csv", "asvspoof_la_test.csv", "asvspoof_la_demo_holdout.csv"):
        with (args.output_dir / name).open(encoding="utf-8", newline="") as stream:
            count = sum(1 for _ in csv.DictReader(stream))
        print(f"{name}_rows={count}")
    print("manifest_build=complete", flush=True)


if __name__ == "__main__":
    main()

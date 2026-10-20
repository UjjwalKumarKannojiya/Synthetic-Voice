"""Build the private, data-free model bundle required by the deployed app."""

from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import os
import tempfile
import zipfile
from pathlib import Path, PureWindowsPath
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
LEGACY_META = Path("models/model_meta.json")
ASV_META = Path("models/asvspoof_la_svm_balanced2500/model_meta.json")
REPORT_PATHS = (
    Path("results/classical_for_2sec.json"),
    Path("results/asvspoof_la_svm_balanced2500.json"),
)


def _clean_report(value: Any) -> Any:
    if isinstance(value, dict):
        cleaned = {}
        for key, item in value.items():
            if key in {"feature_index", "test_scores"}:
                cleaned[key] = None
            elif isinstance(item, str) and (key.endswith("_path") or key.endswith("_file")):
                cleaned[key] = PureWindowsPath(item).name if ":\\" in item else Path(item).name
            else:
                cleaned[key] = _clean_report(item)
        return cleaned
    if isinstance(value, list):
        return [_clean_report(item) for item in value]
    return value


def _model_source(meta_relative: Path) -> tuple[Path, str]:
    meta_path = ROOT / meta_relative
    metadata = json.loads(meta_path.read_text(encoding="utf-8"))
    model_relative = Path(metadata["model_path"])
    if model_relative.is_absolute() or ".." in model_relative.parts:
        raise ValueError(f"Model metadata path is not relative: {meta_relative}")
    model_path = (meta_path.parent / model_relative).resolve()
    if not model_path.is_relative_to((ROOT / "models").resolve()) or not model_path.is_file():
        raise FileNotFoundError(f"Model file required by {meta_relative} is missing")
    bundle_model_path = (Path("models") / meta_relative.parent.relative_to("models") / model_relative).as_posix()
    return model_path, bundle_model_path


def _training_count(manifest_path: Path) -> int:
    count = 0
    with manifest_path.open(encoding="utf-8", newline="") as stream:
        for row in csv.DictReader(stream):
            count += row.get("split") == "training"
    return count


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _sha1(path: Path) -> str:
    digest = hashlib.sha1()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _demo_members(source_root: Path) -> tuple[dict[str, Path | bytes], int]:
    local_only = (ROOT / ".local-notes").resolve()
    source_root = source_root.resolve()
    if not source_root.is_relative_to(local_only) or not source_root.is_dir():
        raise ValueError("Demo assets must be read from an ignored .local-notes directory")
    manifest_path = source_root / "manifest.csv"
    notice_path = source_root / "NOTICE.md"
    if not manifest_path.is_file() or not notice_path.is_file():
        raise FileNotFoundError("Demo assets require manifest.csv and NOTICE.md")
    notice = notice_path.read_text(encoding="utf-8")
    if "ODC-By" not in notice or "CSTR VCTK" not in notice or "development" not in notice.lower():
        raise ValueError("Demo assets are missing dataset attribution or split disclosure")

    with manifest_path.open(encoding="utf-8", newline="") as stream:
        reader = csv.DictReader(stream)
        fields = reader.fieldnames
        if not fields or not {"path", "label", "split", "speaker", "attack_id", "sha1", "name"}.issubset(fields):
            raise ValueError("Demo manifest is missing required sample metadata")
        rows = list(reader)
    if not 4 <= len(rows) <= 12 or len(rows) % 2:
        raise ValueError("Demo manifest must contain 2 to 6 balanced samples per class")
    if any(row["split"] != "val" or row["label"] not in {"0", "1"} for row in rows):
        raise ValueError("Demo assets may only use labeled ASVspoof development clips")
    if any(sum(row["label"] == label for row in rows) != len(rows) // 2 for label in ("0", "1")):
        raise ValueError("Demo manifest must have equal bona fide and spoof sample counts")
    if len({row["speaker"] for row in rows}) != len(rows):
        raise ValueError("Demo clips must use distinct speakers")
    attack_ids = {row["attack_id"] for row in rows if row["label"] == "1"}
    if len(attack_ids) < 2:
        raise ValueError("Demo clips must cover at least two spoof attack systems")

    packaged_rows: list[dict[str, str]] = []
    members: dict[str, Path | bytes] = {"demo/NOTICE.md": notice.encode("utf-8")}
    for row in rows:
        sample_id = row["sha1"].lower()
        if len(sample_id) != 40 or any(char not in "0123456789abcdef" for char in sample_id):
            raise ValueError("Demo sample IDs must be SHA-1 hashes")
        source_relative = Path(row["path"])
        if "\\" in row["path"] or source_relative.is_absolute() or ".." in source_relative.parts or len(source_relative.parts) != 2:
            raise ValueError("Demo audio path must be a local audio/<file>.flac path")
        if source_relative.parts[0] != "audio" or source_relative.suffix.lower() != ".flac":
            raise ValueError("Demo audio path must be a local audio/<file>.flac path")
        source = (source_root / source_relative).resolve()
        if not source.is_relative_to(source_root) or not source.is_file() or _sha1(source) != sample_id:
            raise ValueError("Demo audio is missing or does not match its manifest hash")
        if Path(row["name"]).name != row["name"] or not row["name"].lower().endswith(".flac"):
            raise ValueError("Demo display name is invalid")
        row_copy = dict(row)
        row_copy["path"] = f"audio/{sample_id}.flac"
        packaged_rows.append(row_copy)
        members[f"demo/audio/{sample_id}.flac"] = source

    packaged_manifest = io.StringIO(newline="")
    writer = csv.DictWriter(packaged_manifest, fieldnames=fields, lineterminator="\n")
    writer.writeheader()
    writer.writerows(packaged_rows)
    members["demo/manifest.csv"] = packaged_manifest.getvalue().encode("utf-8")
    return members, len(rows)


def package(output: Path, demo_assets: Path | None = None) -> dict[str, Any]:
    local_only = (ROOT / ".local-notes").resolve()
    output = output.resolve()
    if not output.is_relative_to(local_only):
        raise ValueError("Runtime bundles must be written under the ignored .local-notes directory")
    if output.exists():
        raise FileExistsError(f"Refusing to overwrite existing artifact bundle: {output}")

    legacy_model, legacy_bundle_path = _model_source(LEGACY_META)
    asv_model, asv_bundle_path = _model_source(ASV_META)
    legacy_report_path, asv_report_path = (ROOT / path for path in REPORT_PATHS)
    for path in (legacy_report_path, asv_report_path):
        if not path.is_file():
            raise FileNotFoundError(f"Model evaluation report is required: {path.relative_to(ROOT)}")
    training_manifest = ROOT / "data/manifests/for_2sec.csv"
    if not training_manifest.is_file():
        raise FileNotFoundError("The local FoR manifest is required to derive the real training split count")

    legacy_meta = json.loads((ROOT / LEGACY_META).read_text(encoding="utf-8"))
    asv_meta = json.loads((ROOT / ASV_META).read_text(encoding="utf-8"))
    asv_report = json.loads(asv_report_path.read_text(encoding="utf-8"))
    counts = {
        "legacy_for2sec": _training_count(training_manifest),
        "asvspoof_la_balanced2500": int(asv_report["max_files_per_class"]) * 2,
    }
    runtime_manifest = {
        "schema_version": 1,
        "training_counts": counts,
        "profiles": ["legacy_for2sec", "asvspoof_la_balanced2500"],
    }
    demo_members: dict[str, Path | bytes] = {}
    if demo_assets is not None:
        demo_members, demo_count = _demo_members(demo_assets)
        runtime_manifest["demo_sample_count"] = demo_count

    members: dict[str, bytes | Path] = {
        "models/model_meta.json": (ROOT / LEGACY_META),
        legacy_bundle_path: legacy_model,
        "models/asvspoof_la_svm_balanced2500/model_meta.json": (ROOT / ASV_META),
        asv_bundle_path: asv_model,
        "results/classical_for_2sec.json": json.dumps(
            _clean_report(json.loads(legacy_report_path.read_text(encoding="utf-8"))),
            separators=(",", ":"),
        ).encode("utf-8"),
        "results/asvspoof_la_svm_balanced2500.json": json.dumps(
            _clean_report(asv_report), separators=(",", ":")
        ).encode("utf-8"),
        "runtime_manifest.json": json.dumps(runtime_manifest, separators=(",", ":")).encode("utf-8"),
    }
    members.update(demo_members)
    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(prefix="voiceguard-bundle-", suffix=".zip", dir=output.parent, delete=False) as temporary:
        temporary_path = Path(temporary.name)
    try:
        with zipfile.ZipFile(temporary_path, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
            for name, source in members.items():
                if isinstance(source, Path):
                    archive.write(source, name)
                else:
                    archive.writestr(name, source)
        if temporary_path.stat().st_size > 32 * 1024 * 1024:
            raise ValueError("The private artifact bundle exceeds the 32 MiB deployment limit")
        os.replace(temporary_path, output)
    except Exception:
        temporary_path.unlink(missing_ok=True)
        raise
    return {
        "path": str(output),
        "bytes": output.stat().st_size,
        "sha256": _sha256(output),
        "members": list(members),
        "training_counts": counts,
        "full_dataset_audio_included": False,
        "demo_audio_included": demo_assets is not None,
        "demo_sample_count": runtime_manifest.get("demo_sample_count", 0),
        "dataset_manifests_included": False,
        "active_model_files": [legacy_bundle_path, asv_bundle_path],
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output",
        type=Path,
        default=Path(".local-notes/deployment/voiceguard-runtime-r9-demo.zip"),
    )
    parser.add_argument(
        "--demo-assets",
        type=Path,
        default=Path(".local-notes/demo-assets-r9"),
        help="Ignored local directory produced by scripts/prepare_demo_assets.py",
    )
    args = parser.parse_args()
    print(json.dumps(package(ROOT / args.output, ROOT / args.demo_assets), indent=2))


if __name__ == "__main__":
    main()

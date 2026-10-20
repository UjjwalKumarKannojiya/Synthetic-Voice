"""Build the private, data-free model bundle required by the deployed app."""

from __future__ import annotations

import argparse
import csv
import hashlib
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


def package(output: Path) -> dict[str, Any]:
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
        "dataset_audio_included": False,
        "dataset_manifests_included": False,
        "active_model_files": [legacy_bundle_path, asv_bundle_path],
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output",
        type=Path,
        default=Path(".local-notes/deployment/voiceguard-runtime.zip"),
    )
    args = parser.parse_args()
    print(json.dumps(package(ROOT / args.output), indent=2))


if __name__ == "__main__":
    main()

"""Verified model/report artifact loading for read-only serverless runtimes."""

from __future__ import annotations

import hashlib
import csv
import io
import json
import os
import re
import shutil
import stat
import tempfile
import urllib.error
import urllib.parse
import urllib.request
import zipfile
from pathlib import Path, PurePosixPath
from typing import Any, Mapping


ARTIFACT_MEMBERS = frozenset(
    {
        "models/model_meta.json",
        "models/classical_for_2sec/svm.joblib",
        "models/asvspoof_la_svm_balanced2500/model_meta.json",
        "models/asvspoof_la_svm_balanced2500/svm.joblib",
        "results/classical_for_2sec.json",
        "results/asvspoof_la_svm_balanced2500.json",
        "runtime_manifest.json",
    }
)
DEMO_MANIFEST_MEMBER = "demo/manifest.csv"
DEMO_NOTICE_MEMBER = "demo/NOTICE.md"
DEMO_AUDIO_PREFIX = "demo/audio/"
MAX_DEMO_SAMPLES = 12
MAX_ARCHIVE_BYTES = 32 * 1024 * 1024
MAX_EXPANDED_BYTES = 64 * 1024 * 1024
_SHA256_RE = re.compile(r"^[a-f0-9]{64}$")


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _demo_bundle_members(archive: zipfile.ZipFile, names: set[str]) -> set[str]:
    extras = names - ARTIFACT_MEMBERS
    if not extras:
        return set()
    if DEMO_MANIFEST_MEMBER not in extras or DEMO_NOTICE_MEMBER not in extras:
        raise ValueError("Runtime artifact bundle contains an unexpected file set")
    try:
        manifest_text = archive.read(DEMO_MANIFEST_MEMBER).decode("utf-8")
        rows = list(csv.DictReader(io.StringIO(manifest_text, newline="")))
        notice = archive.read(DEMO_NOTICE_MEMBER).decode("utf-8")
    except (KeyError, UnicodeDecodeError, OSError) as exc:
        raise ValueError("Runtime demo manifest or attribution notice is invalid") from exc
    required = {"path", "label", "split", "speaker", "attack_id", "sha1", "name"}
    if not rows or not required.issubset(rows[0]):
        raise ValueError("Runtime demo manifest is missing sample metadata")
    if len(rows) > MAX_DEMO_SAMPLES or len(rows) < 4 or len(rows) % 2:
        raise ValueError("Runtime demo manifest has an invalid sample count")
    if any(row["split"] != "val" or row["label"] not in {"0", "1"} for row in rows):
        raise ValueError("Runtime demo manifest must use labeled development samples")
    if any(sum(row["label"] == label for row in rows) != len(rows) // 2 for label in ("0", "1")):
        raise ValueError("Runtime demo manifest is not class-balanced")
    sample_ids = [row["sha1"].lower() for row in rows]
    if any(not re.fullmatch(r"[a-f0-9]{40}", sample_id) for sample_id in sample_ids):
        raise ValueError("Runtime demo sample IDs are invalid")
    if len(sample_ids) != len(set(sample_ids)) or len({row["speaker"] for row in rows}) != len(rows):
        raise ValueError("Runtime demo samples contain duplicate IDs or speakers")
    if len({row["attack_id"] for row in rows if row["label"] == "1"}) < 2:
        raise ValueError("Runtime demo samples must cover multiple spoof attacks")
    if any(
        "\\" in row["path"]
        or row["path"] != f"audio/{sample_id}.flac"
        or Path(row["name"]).name != row["name"]
        or not row["name"].lower().endswith(".flac")
        for row, sample_id in zip(rows, sample_ids, strict=True)
    ):
        raise ValueError("Runtime demo manifest contains an unsafe audio path or name")
    if "ASVspoof 2019" not in notice or "ODC-By" not in notice or "CSTR VCTK" not in notice:
        raise ValueError("Runtime demo attribution notice is missing")

    expected_audio = {f"{DEMO_AUDIO_PREFIX}{sample_id}.flac" for sample_id in sample_ids}
    expected = {DEMO_MANIFEST_MEMBER, DEMO_NOTICE_MEMBER, *expected_audio}
    if extras != expected:
        raise ValueError("Runtime artifact bundle contains an unexpected file set")
    for info in archive.infolist():
        if info.filename in expected_audio:
            sample_id = Path(info.filename).stem
            if info.file_size > 8 * 1024 * 1024:
                raise ValueError("Runtime demo audio file exceeds the size limit")
            if hashlib.sha1(archive.read(info.filename)).hexdigest() != sample_id:
                raise ValueError("Runtime demo audio hash does not match its manifest")
    return expected


def _validate_bundle(archive_path: Path, expected_sha256: str, destination: Path) -> None:
    if not _SHA256_RE.fullmatch(expected_sha256):
        raise ValueError("VOICEGUARD_ARTIFACTS_SHA256 must be a 64-character SHA-256 hex digest")
    if _sha256_file(archive_path) != expected_sha256:
        raise ValueError("Runtime artifact bundle checksum does not match its configured digest")

    try:
        with zipfile.ZipFile(archive_path) as archive:
            infos = archive.infolist()
            names = [info.filename for info in infos]
            if len(names) != len(set(names)):
                raise ValueError("Runtime artifact bundle contains an unexpected file set")
            expected_members = ARTIFACT_MEMBERS | _demo_bundle_members(archive, set(names))
            if set(names) != expected_members:
                raise ValueError("Runtime artifact bundle contains an unexpected file set")
            if sum(info.file_size for info in infos) > MAX_EXPANDED_BYTES:
                raise ValueError("Runtime artifact bundle expands beyond the allowed size")
            for info in infos:
                member = PurePosixPath(info.filename)
                mode = info.external_attr >> 16
                if (
                    member.is_absolute()
                    or ".." in member.parts
                    or "\\" in info.filename
                    or stat.S_ISLNK(mode)
                    or info.is_dir()
                ):
                    raise ValueError("Runtime artifact bundle contains an unsafe path")
                output = destination.joinpath(*member.parts)
                output.parent.mkdir(parents=True, exist_ok=True)
                with archive.open(info) as source, output.open("wb") as target:
                    shutil.copyfileobj(source, target, length=1024 * 1024)
                if output.stat().st_size != info.file_size:
                    raise ValueError("Runtime artifact bundle has a truncated member")
    except (zipfile.BadZipFile, OSError) as exc:
        raise ValueError("Runtime artifact bundle could not be read") from exc

    for relative in ARTIFACT_MEMBERS - {"runtime_manifest.json"}:
        if not (destination / relative).is_file():
            raise ValueError("Runtime artifact bundle is missing a required file")

    manifest_path = destination / "runtime_manifest.json"
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        if manifest.get("schema_version") != 1:
            raise ValueError
        counts = manifest["training_counts"]
        if any(type(counts[key]) is not int or counts[key] < 0 for key in ("legacy_for2sec", "asvspoof_la_balanced2500")):
            raise ValueError
        demo_count = manifest.get("demo_sample_count", 0)
        if type(demo_count) is not int or demo_count < 0 or demo_count > MAX_DEMO_SAMPLES:
            raise ValueError
        has_demo_assets = (destination / DEMO_MANIFEST_MEMBER).is_file()
        if has_demo_assets != (demo_count > 0):
            raise ValueError
        if has_demo_assets:
            with (destination / DEMO_MANIFEST_MEMBER).open(encoding="utf-8", newline="") as stream:
                if sum(1 for _ in csv.DictReader(stream)) != demo_count:
                    raise ValueError
    except (OSError, KeyError, TypeError, json.JSONDecodeError, ValueError) as exc:
        raise ValueError("Runtime artifact training-count manifest is invalid") from exc

    for relative in (
        "models/model_meta.json",
        "models/asvspoof_la_svm_balanced2500/model_meta.json",
    ):
        try:
            metadata = json.loads((destination / relative).read_text(encoding="utf-8"))
            model_path = PurePosixPath(metadata["model_path"])
            if not all(key in metadata for key in ("model_version", "sample_rate", "threshold", "mfcc")):
                raise ValueError
        except (OSError, KeyError, TypeError, json.JSONDecodeError, ValueError) as exc:
            raise ValueError("Runtime model metadata is invalid") from exc
        if model_path.is_absolute() or ".." in model_path.parts or "\\" in metadata["model_path"] or ":" in metadata["model_path"]:
            raise ValueError("Runtime model metadata contains an unsafe model path")
        if not (destination / Path(relative).parent.joinpath(*model_path.parts)).is_file():
            raise ValueError("Runtime model metadata points to a missing model file")

    for relative in ("results/classical_for_2sec.json", "results/asvspoof_la_svm_balanced2500.json"):
        try:
            if not isinstance(json.loads((destination / relative).read_text(encoding="utf-8")), dict):
                raise ValueError
        except (OSError, json.JSONDecodeError, ValueError) as exc:
            raise ValueError("Runtime evaluation report is invalid") from exc


def install_runtime_bundle(url: str, expected_sha256: str, token: str | None = None) -> Path:
    """Download and validate a private HTTPS bundle into Vercel's writable /tmp."""

    if not _SHA256_RE.fullmatch(expected_sha256):
        raise RuntimeError("Deployment requires VOICEGUARD_ARTIFACTS_SHA256 with a valid SHA-256 digest")
    parsed = urllib.parse.urlsplit(url)
    if parsed.scheme != "https" or not parsed.netloc:
        raise RuntimeError("VOICEGUARD_ARTIFACTS_URL must be a private HTTPS download URL")

    cache_root = Path(tempfile.gettempdir()).resolve()
    cache = cache_root / f"voiceguard-runtime-{expected_sha256}"
    marker = cache / ".verified-sha256"
    if marker.is_file() and marker.read_text(encoding="ascii").strip() == expected_sha256:
        return cache
    if cache.exists():
        raise RuntimeError("An incomplete runtime artifact cache exists; use a new artifact checksum")

    headers = {"User-Agent": "VoiceGuard-runtime/1"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    request = urllib.request.Request(url, headers=headers)
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            if response.status != 200:
                raise RuntimeError("Private runtime artifact download returned a non-200 response")
            length = response.headers.get("Content-Length")
            if length and int(length) > MAX_ARCHIVE_BYTES:
                raise RuntimeError("Runtime artifact bundle exceeds the allowed download size")
            with tempfile.TemporaryDirectory(prefix="voiceguard-artifacts-") as temporary:
                temporary_root = Path(temporary)
                archive_path = temporary_root / "bundle.zip"
                total = 0
                with archive_path.open("wb") as stream:
                    while chunk := response.read(1024 * 1024):
                        total += len(chunk)
                        if total > MAX_ARCHIVE_BYTES:
                            raise RuntimeError("Runtime artifact bundle exceeds the allowed download size")
                        stream.write(chunk)
                unpacked = temporary_root / "unpacked"
                unpacked.mkdir()
                _validate_bundle(archive_path, expected_sha256, unpacked)
                (unpacked / ".verified-sha256").write_text(expected_sha256, encoding="ascii")
                try:
                    os.replace(unpacked, cache)
                except OSError:
                    if not (cache / ".verified-sha256").is_file():
                        raise
                return cache
    except urllib.error.URLError:
        # The configured URL can be signed; do not expose it through chained startup logs.
        raise RuntimeError("Private runtime artifact download failed") from None


def prepare_runtime_artifacts(project_root: Path, environ: Mapping[str, str] | None = None) -> Path:
    """Use local artifacts in development; require verified external artifacts on Vercel."""

    env = os.environ if environ is None else environ
    if env.get("VERCEL") != "1":
        return project_root
    url = env.get("VOICEGUARD_ARTIFACTS_URL", "").strip()
    digest = env.get("VOICEGUARD_ARTIFACTS_SHA256", "").strip().lower()
    if not url:
        raise RuntimeError("Deployment requires private model artifacts; set VOICEGUARD_ARTIFACTS_URL")
    if not digest:
        raise RuntimeError("Deployment requires VOICEGUARD_ARTIFACTS_SHA256")
    token = env.get("VOICEGUARD_ARTIFACTS_TOKEN")
    hostname = urllib.parse.urlsplit(url).hostname or ""
    if not token and hostname.endswith(".private.blob.vercel-storage.com"):
        # Prefer Vercel's short-lived project OIDC token; the connected store's
        # read-write token is a fallback. Never send either to another host.
        token = env.get("VERCEL_OIDC_TOKEN") or env.get("BLOB_READ_WRITE_TOKEN")
    return install_runtime_bundle(url, digest, token)

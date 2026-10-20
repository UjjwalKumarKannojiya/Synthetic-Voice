"""Verified model/report artifact loading for read-only serverless runtimes."""

from __future__ import annotations

import hashlib
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
MAX_ARCHIVE_BYTES = 32 * 1024 * 1024
MAX_EXPANDED_BYTES = 64 * 1024 * 1024
_SHA256_RE = re.compile(r"^[a-f0-9]{64}$")


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _validate_bundle(archive_path: Path, expected_sha256: str, destination: Path) -> None:
    if not _SHA256_RE.fullmatch(expected_sha256):
        raise ValueError("VOICEGUARD_ARTIFACTS_SHA256 must be a 64-character SHA-256 hex digest")
    if _sha256_file(archive_path) != expected_sha256:
        raise ValueError("Runtime artifact bundle checksum does not match its configured digest")

    try:
        with zipfile.ZipFile(archive_path) as archive:
            infos = archive.infolist()
            names = [info.filename for info in infos]
            if len(names) != len(set(names)) or set(names) != ARTIFACT_MEMBERS:
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
    return install_runtime_bundle(url, digest, env.get("VOICEGUARD_ARTIFACTS_TOKEN"))

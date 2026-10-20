from __future__ import annotations

import hashlib
import io
import csv
import json
import urllib.error
import zipfile
from pathlib import Path

import pytest
import app.db.database as database_module

from app import deployment_artifacts
from app.deployment_artifacts import ARTIFACT_MEMBERS, _validate_bundle, prepare_runtime_artifacts
from app.db.database import Database


def _valid_members() -> dict[str, bytes]:
    return {
        "models/model_meta.json": json.dumps({
            "model_path": "classical_for_2sec/svm.joblib", "model_version": "fixture-window",
            "sample_rate": 16000, "threshold": 0.5, "mfcc": {},
        }).encode(),
        "models/classical_for_2sec/svm.joblib": b"fixture legacy model",
        "models/asvspoof_la_svm_balanced2500/model_meta.json": json.dumps({
            "model_path": "svm.joblib", "model_version": "fixture-clip",
            "sample_rate": 16000, "threshold": 0.5, "mfcc": {},
        }).encode(),
        "models/asvspoof_la_svm_balanced2500/svm.joblib": b"fixture clip model",
        "results/classical_for_2sec.json": b"{}",
        "results/asvspoof_la_svm_balanced2500.json": b"{}",
        "runtime_manifest.json": json.dumps(
            {"schema_version": 1, "training_counts": {"legacy_for2sec": 10, "asvspoof_la_balanced2500": 20}}
        ).encode(),
    }


def _write_bundle(path: Path, members: dict[str, bytes]) -> str:
    with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for name, content in members.items():
            archive.writestr(name, content)
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _with_demo_members(members: dict[str, bytes]) -> dict[str, bytes]:
    rows = []
    speakers = ("speaker-a", "speaker-b", "speaker-c", "speaker-d")
    labels = ("0", "0", "1", "1")
    for index, (speaker, label) in enumerate(zip(speakers, labels, strict=True)):
        audio = f"licensed-demo-fixture-{index}".encode()
        sample_id = hashlib.sha1(audio).hexdigest()
        name = f"LA_D_fixture{index}.flac"
        rows.append({
            "path": f"audio/{sample_id}.flac",
            "label": label,
            "split": "val",
            "speaker": speaker,
            "attack_id": "-" if label == "0" else f"A0{index}",
            "sr": "16000",
            "duration_s": "2.0",
            "sha1": sample_id,
            "name": name,
        })
        members[f"demo/audio/{sample_id}.flac"] = audio
    output = io.StringIO(newline="")
    writer = csv.DictWriter(output, fieldnames=rows[0].keys(), lineterminator="\n")
    writer.writeheader()
    writer.writerows(rows)
    members["demo/manifest.csv"] = output.getvalue().encode()
    members["demo/NOTICE.md"] = (
        "ASVspoof 2019 LA development subset. ODC-By 1.0. CSTR VCTK CC BY 4.0."
    ).encode()
    runtime = json.loads(members["runtime_manifest.json"])
    runtime["demo_sample_count"] = len(rows)
    members["runtime_manifest.json"] = json.dumps(runtime).encode()
    return members


def test_verified_bundle_extracts_only_runtime_files(tmp_path: Path) -> None:
    archive = tmp_path / "runtime.zip"
    destination = tmp_path / "unpacked"
    digest = _write_bundle(archive, _valid_members())

    _validate_bundle(archive, digest, destination)

    assert {p.relative_to(destination).as_posix() for p in destination.rglob("*") if p.is_file()} == ARTIFACT_MEMBERS
    assert json.loads((destination / "runtime_manifest.json").read_text())["training_counts"]["legacy_for2sec"] == 10


def test_verified_bundle_accepts_attributed_balanced_demo_assets(tmp_path: Path) -> None:
    archive = tmp_path / "runtime-with-demo.zip"
    destination = tmp_path / "unpacked-with-demo"
    members = _with_demo_members(_valid_members())
    digest = _write_bundle(archive, members)

    _validate_bundle(archive, digest, destination)

    files = {path.relative_to(destination).as_posix() for path in destination.rglob("*") if path.is_file()}
    assert files == ARTIFACT_MEMBERS | (set(members) - ARTIFACT_MEMBERS)
    assert json.loads((destination / "runtime_manifest.json").read_text())["demo_sample_count"] == 4


def test_demo_bundle_rejects_audio_that_does_not_match_manifest_hash(tmp_path: Path) -> None:
    archive = tmp_path / "runtime-bad-demo.zip"
    members = _with_demo_members(_valid_members())
    audio_name = next(name for name in members if name.startswith("demo/audio/"))
    members[audio_name] = b"tampered"
    digest = _write_bundle(archive, members)

    with pytest.raises(ValueError, match="audio hash"):
        _validate_bundle(archive, digest, tmp_path / "unpacked")


def test_bundle_checksum_must_match(tmp_path: Path) -> None:
    archive = tmp_path / "runtime.zip"
    _write_bundle(archive, _valid_members())

    with pytest.raises(ValueError, match="checksum"):
        _validate_bundle(archive, "0" * 64, tmp_path / "unpacked")


def test_bundle_rejects_unexpected_files(tmp_path: Path) -> None:
    archive = tmp_path / "runtime.zip"
    members = _valid_members()
    members["data/audio.wav"] = b"must not ship"
    digest = _write_bundle(archive, members)

    with pytest.raises(ValueError, match="unexpected file set"):
        _validate_bundle(archive, digest, tmp_path / "unpacked")


def test_bundle_rejects_unsafe_model_paths(tmp_path: Path) -> None:
    archive = tmp_path / "runtime.zip"
    members = _valid_members()
    members["models/model_meta.json"] = json.dumps({
        "model_path": "../../outside.joblib", "model_version": "fixture-window",
        "sample_rate": 16000, "threshold": 0.5, "mfcc": {},
    }).encode()
    digest = _write_bundle(archive, members)

    with pytest.raises(ValueError, match="unsafe model path"):
        _validate_bundle(archive, digest, tmp_path / "unpacked")


def test_vercel_requires_private_artifact_configuration(tmp_path: Path) -> None:
    with pytest.raises(RuntimeError, match="VOICEGUARD_ARTIFACTS_URL"):
        prepare_runtime_artifacts(tmp_path, {"VERCEL": "1"})


def test_vercel_rejects_ephemeral_sqlite_database(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("VERCEL", "1")
    with pytest.raises(RuntimeError, match="persistent PostgreSQL"):
        Database(tmp_path / "ephemeral.sqlite3")


def test_vercel_supabase_transaction_pooler_disables_client_pool_and_prepares(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("VERCEL", "1")
    captured = {}

    def fake_create_engine(url, **kwargs):
        captured["url"] = url
        captured.update(kwargs)
        return object()

    monkeypatch.setattr(database_module.sa, "create_engine", fake_create_engine)

    database = Database("postgresql://db-user:fixture-password@aws-0-test.pooler.supabase.com:6543/postgres")

    assert database.engine is not None
    assert captured["poolclass"] is database_module.NullPool
    assert captured["connect_args"]["prepare_threshold"] is None
    assert "pool_size" not in captured


def test_postgres_url_decodes_percent_encoded_reserved_password_characters() -> None:
    parsed = database_module.make_url(
        "postgresql://db-user:fixture%40password%23@aws-0-test.pooler.supabase.com:6543/postgres"
    )

    assert parsed.host == "aws-0-test.pooler.supabase.com"
    assert parsed.password == "fixture@password#"


def test_vercel_download_verifies_and_caches_private_bundle(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    archive_path = tmp_path / "source.zip"
    digest = _write_bundle(archive_path, _valid_members())
    content = archive_path.read_bytes()
    requested = {}

    class FakeResponse(io.BytesIO):
        status = 200
        headers = {"Content-Length": str(len(content))}

        def __enter__(self):
            return self

        def __exit__(self, *_args):
            self.close()

    def fake_urlopen(request, timeout):
        requested["url"] = request.full_url
        requested["authorization"] = request.get_header("Authorization")
        requested["timeout"] = timeout
        return FakeResponse(content)

    monkeypatch.setattr(deployment_artifacts.tempfile, "gettempdir", lambda: str(tmp_path))
    monkeypatch.setattr(deployment_artifacts.urllib.request, "urlopen", fake_urlopen)
    configured = {
        "VERCEL": "1",
        "VOICEGUARD_ARTIFACTS_URL": "https://private.invalid/runtime.zip",
        "VOICEGUARD_ARTIFACTS_SHA256": digest,
        "VOICEGUARD_ARTIFACTS_TOKEN": "unit-test-token",
    }

    installed = prepare_runtime_artifacts(tmp_path, configured)

    assert installed == tmp_path / f"voiceguard-runtime-{digest}"
    assert (installed / ".verified-sha256").read_text(encoding="ascii") == digest
    assert (installed / "models/classical_for_2sec/svm.joblib").read_bytes() == b"fixture legacy model"
    assert requested == {
        "url": "https://private.invalid/runtime.zip",
        "authorization": "Bearer unit-test-token",
        "timeout": 30,
    }


def test_download_errors_do_not_expose_signed_url(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(deployment_artifacts.tempfile, "gettempdir", lambda: str(tmp_path))

    def fail_with_signed_url(_request, timeout):
        raise urllib.error.URLError("https://private.invalid/runtime.zip?secret=do-not-log")

    monkeypatch.setattr(deployment_artifacts.urllib.request, "urlopen", fail_with_signed_url)
    with pytest.raises(RuntimeError, match="download failed") as error:
        deployment_artifacts.install_runtime_bundle(
            "https://private.invalid/runtime.zip?secret=do-not-log",
            "a" * 64,
        )

    assert "do-not-log" not in str(error.value)
    assert error.value.__suppress_context__ is True


def test_vercel_oidc_token_is_scoped_to_private_blob_hosts(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    calls = []

    def capture_install(url, digest, token=None):
        calls.append((url, digest, token))
        return tmp_path

    monkeypatch.setattr(deployment_artifacts, "install_runtime_bundle", capture_install)
    common = {
        "VERCEL": "1",
        "VOICEGUARD_ARTIFACTS_SHA256": "a" * 64,
        "VERCEL_OIDC_TOKEN": "short-lived-test-token",
        "BLOB_READ_WRITE_TOKEN": "private-blob-test-token",
    }
    blob_url = "https://store.private.blob.vercel-storage.com/runtime.zip"
    static_blob_url = "https://store.private.blob.vercel-storage.com/runtime-static-token.zip"
    other_url = "https://private.invalid/runtime.zip"

    prepare_runtime_artifacts(tmp_path, {**common, "VOICEGUARD_ARTIFACTS_URL": blob_url})
    prepare_runtime_artifacts(
        tmp_path,
        {**common, "VOICEGUARD_ARTIFACTS_URL": static_blob_url, "VERCEL_OIDC_TOKEN": ""},
    )
    prepare_runtime_artifacts(tmp_path, {**common, "VOICEGUARD_ARTIFACTS_URL": other_url})

    assert calls == [
        (blob_url, "a" * 64, "short-lived-test-token"),
        (static_blob_url, "a" * 64, "private-blob-test-token"),
        (other_url, "a" * 64, None),
    ]

"""FastAPI application for the VoiceGuard research prototype."""

from __future__ import annotations

import json
import hashlib
import csv
import os
import re
import tempfile
import time
from contextlib import asynccontextmanager
from functools import lru_cache
from pathlib import Path
from typing import Any
from urllib.parse import quote, urlsplit

from scipy.signal import resample_poly
from fastapi import FastAPI, File, HTTPException, Query, Request, Response, UploadFile, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse, HTMLResponse, PlainTextResponse, RedirectResponse
from pydantic import BaseModel, Field, model_validator

from .core.auth import (
    LOGIN_FAILURE_LIMIT,
    LOGIN_WINDOW_SECONDS,
    SESSION_SECONDS,
    SIGNUP_LIMIT,
    SIGNUP_WINDOW_SECONDS,
    auth_attempt_count,
    auth_ip_attempt_count,
    consume_ws_ticket,
    create_account,
    create_session,
    create_ws_ticket,
    delete_session,
    hash_password,
    record_auth_attempt,
    session_user,
    validate_password,
    verify_account,
)
from .core.audio_utils import decode_audio_file
from .core.detector import Detector, DetectorConfig
from .core.asvspoof_detector import ASVspoofDetector
from .core.audio_utils import pcm16_to_float32
from .core.streaming import StreamSession
from .db.crud import (
    clear_analyses,
    dashboard_summary,
    export_csv,
    get_analysis,
    list_analyses,
    read_settings,
    save_analysis,
    write_settings,
)
from .db.database import Database
from .deployment_artifacts import prepare_runtime_artifacts


ROOT = Path(__file__).resolve().parents[1]
DATABASE_URL = os.environ.get("DATABASE_URL")
if os.environ.get("VERCEL") == "1" and not DATABASE_URL:
    raise RuntimeError("DATABASE_URL must point to persistent hosted PostgreSQL on Vercel")
DATABASE = Database(DATABASE_URL or ROOT / "data" / "voiceguard.sqlite3")
MAX_UPLOAD_BYTES = (4 if os.environ.get("VERCEL") == "1" else 10) * 1024 * 1024
DEFAULT_SETTINGS = {
    "uncertain_band": 0.05,
    "hop_seconds": 1.0,
    "vad_threshold": 0.01,
    "smoothing_alpha": 0.4,
    "alert_consecutive_windows": 3,
}
MODEL_PROFILES = {
    "legacy_for2sec": {
        "meta": ROOT / "models" / "model_meta.json",
        "report": ROOT / "results" / "classical_for_2sec.json",
        "kind": "windowed",
    },
    "asvspoof_la_balanced2500": {
        "meta": ROOT / "models" / "asvspoof_la_svm_balanced2500" / "model_meta.json",
        "report": ROOT / "results" / "asvspoof_la_svm_balanced2500.json",
        "kind": "clip",
    },
}
RUNTIME_MANIFEST = ROOT / "runtime_manifest.json"
DEMO_MANIFEST = ROOT / "data" / "manifests" / "asvspoof_la_demo_holdout.csv"


def configure_artifact_root(artifact_root: Path) -> None:
    """Point model/report reads at verified writable storage on Vercel."""

    global MODEL_PROFILES, RUNTIME_MANIFEST
    MODEL_PROFILES = {
        "legacy_for2sec": {
            "meta": artifact_root / "models" / "model_meta.json",
            "report": artifact_root / "results" / "classical_for_2sec.json",
            "kind": "windowed",
        },
        "asvspoof_la_balanced2500": {
            "meta": artifact_root / "models" / "asvspoof_la_svm_balanced2500" / "model_meta.json",
            "report": artifact_root / "results" / "asvspoof_la_svm_balanced2500.json",
            "kind": "clip",
        },
    }
    RUNTIME_MANIFEST = artifact_root / "runtime_manifest.json"
    training_count.cache_clear()
    _load_legacy_detector.cache_clear()
    _load_asvspoof_detector.cache_clear()


class SettingsPayload(BaseModel):
    threshold: float = Field(ge=0.0, le=1.0)
    uncertain_band: float = Field(0.05, ge=0.0, le=1.0)
    hop_seconds: float = Field(1.0, ge=1 / 16000, le=2.0)
    vad_threshold: float = Field(0.01, ge=0.0, le=1.0)
    smoothing_alpha: float = Field(0.4, gt=0.0, le=1.0)
    alert_consecutive_windows: int = Field(3, ge=1, le=100)


class AuthPayload(BaseModel):
    username: str | None = Field(default=None, min_length=3, max_length=40, pattern=r"^[A-Za-z0-9_.-]+$")
    email: str | None = Field(default=None, max_length=320)
    display_name: str | None = Field(default=None, max_length=120)
    password: str = Field(min_length=10, max_length=128)

    @model_validator(mode="after")
    def validate_identity(self) -> AuthPayload:
        if not self.username and not self.email:
            raise ValueError("Enter an email address.")
        if self.email and not re.fullmatch(r"[^\s@]+@[^\s@]+\.[^\s@]+", self.email.strip()):
            raise ValueError("Enter a valid email address.")
        return self

    @property
    def identity(self) -> str:
        return (self.email or self.username or "").strip()


class ChangePasswordPayload(BaseModel):
    current_password: str = Field(min_length=1, max_length=128)
    new_password: str = Field(min_length=10, max_length=128)


class DeleteAccountPayload(BaseModel):
    password: str = Field(min_length=1, max_length=128)


@lru_cache(maxsize=None)
def training_count(profile: str) -> int:
    if RUNTIME_MANIFEST.is_file():
        manifest = json.loads(RUNTIME_MANIFEST.read_text(encoding="utf-8"))
        count = manifest.get("training_counts", {}).get(profile)
        if isinstance(count, int) and count >= 0:
            return count
    if profile == "asvspoof_la_balanced2500":
        report = json.loads(MODEL_PROFILES[profile]["report"].read_text(encoding="utf-8"))
        return int(report["max_files_per_class"]) * 2
    manifest = ROOT / "data" / "manifests" / "for_2sec.csv"
    with manifest.open(encoding="utf-8", newline="") as stream:
        return sum(1 for row in csv.DictReader(stream) if row.get("split") == "training")


def current_settings(profile: str = "legacy_for2sec", user_id: int | None = None) -> dict[str, Any]:
    values = DEFAULT_SETTINGS.copy()
    saved = read_settings(DATABASE, user_id)
    values.update({key: value for key, value in saved.items() if key in values})
    meta_path = MODEL_PROFILES[profile]["meta"]
    if not meta_path.exists():
        raise HTTPException(status_code=503, detail=f"Model metadata is unavailable for profile {profile}")
    meta = json.loads(meta_path.read_text(encoding="utf-8"))
    values["threshold"] = float(saved.get(f"threshold:{profile}", meta["threshold"]))
    return values


def build_detector(user_id: int | None = None) -> Detector:
    settings = current_settings("legacy_for2sec", user_id)
    return _load_legacy_detector(
        str(MODEL_PROFILES["legacy_for2sec"]["meta"]),
        float(settings["hop_seconds"]),
        float(settings["uncertain_band"]),
        float(settings["vad_threshold"]),
        float(settings["threshold"]),
    )


@lru_cache(maxsize=8)
def _load_legacy_detector(meta_path: str, hop_seconds: float, uncertain_band: float, vad_threshold: float, threshold: float) -> Detector:
    return Detector(meta_path=meta_path, config=DetectorConfig(
        hop_seconds=hop_seconds,
        uncertain_band=uncertain_band,
        vad_threshold=vad_threshold,
        threshold=threshold,
    ))


@lru_cache(maxsize=8)
def _load_asvspoof_detector(meta_path: str, uncertain_band: float, threshold: float) -> ASVspoofDetector:
    return ASVspoofDetector(meta_path=meta_path, uncertain_band=uncertain_band, threshold=threshold)


def build_profile_detector(profile: str, user_id: int | None = None) -> Detector | ASVspoofDetector:
    if profile == "legacy_for2sec":
        return build_detector(user_id)
    if profile == "asvspoof_la_balanced2500":
        settings = current_settings(profile, user_id)
        return _load_asvspoof_detector(
            str(MODEL_PROFILES[profile]["meta"]),
            float(settings["uncertain_band"]),
            float(settings["threshold"]),
        )
    raise HTTPException(status_code=400, detail=f"Unknown model profile: {profile}")


def profile_info(profile: str, user_id: int | None = None) -> dict[str, Any]:
    details = MODEL_PROFILES.get(profile)
    if details is None:
        raise HTTPException(status_code=400, detail=f"Unknown model profile: {profile}")
    if not details["meta"].is_file() or not details["report"].is_file():
        raise HTTPException(status_code=503, detail=f"Model metadata or evaluation report is unavailable for profile {profile}")
    meta = json.loads(details["meta"].read_text(encoding="utf-8"))
    model_file = details["meta"].parent / meta["model_path"]
    if not model_file.is_file():
        raise HTTPException(status_code=503, detail=f"Model weights are unavailable for profile {profile}")
    report = json.loads(details["report"].read_text(encoding="utf-8"))
    settings = current_settings(profile, user_id)
    if profile == "legacy_for2sec":
        splits = {
            "training": training_count(profile),
            "validation": report["models"]["svm"]["validation"]["count"],
            "testing": report["models"]["svm"]["test"]["count"],
        }

        model_type = "SVM with RBF kernel and probability estimates"
        feature_details = "20 coefficients with mean/std summaries (120 values total)"
    else:
        splits = {
            "training": training_count(profile),
            "validation": report["validation"]["count"],
            "testing": report["test"]["count"],
        }
        model_type = "ASVspoof LA SVM with balanced subset training"
        feature_details = "Complete variable-duration clip; 20 coefficients with mean/std summaries"
    return {
        "profile": profile,
        "name": meta["name"],
        "model_type": model_type,
        "features": "MFCC + delta + delta-delta summary",
        "feature_details": feature_details,
        "training_dataset": meta["training_dataset"],
        "data_split": splits,
        "window_s": meta["window_seconds"],
        "sample_rate": meta["sample_rate"],
        "threshold": settings["threshold"],
        "uncertain_band": settings["uncertain_band"],
        "model_version": meta["model_version"],
        "model_hash": hashlib.sha256(model_file.read_bytes()).hexdigest(),
        "score_definition": meta["score_definition"],
        "inference_kind": details["kind"],
    }


def demo_samples() -> list[dict[str, Any]]:
    if not DEMO_MANIFEST.exists():
        raise HTTPException(status_code=503, detail="Demo holdout manifest is unavailable")
    with DEMO_MANIFEST.open(encoding="utf-8", newline="") as stream:
        rows = list(csv.DictReader(stream))
    samples = []
    for row in rows:
        path = Path(row["path"])
        samples.append({
            "id": row["sha1"],
            "name": path.name,
            "duration_s": float(row["duration_s"]),
        })
    return samples


def demo_row(sample_id: str) -> dict[str, str]:
    if not DEMO_MANIFEST.exists():
        raise HTTPException(status_code=503, detail="Demo holdout manifest is unavailable")
    with DEMO_MANIFEST.open(encoding="utf-8", newline="") as stream:
        for row in csv.DictReader(stream):
            if row["sha1"] == sample_id:
                return row
    raise HTTPException(status_code=404, detail="Demo sample not found")


@asynccontextmanager
async def lifespan(_: FastAPI):
    configure_artifact_root(prepare_runtime_artifacts(ROOT))
    DATABASE.initialize()
    if not read_settings(DATABASE):
        write_settings(DATABASE, DEFAULT_SETTINGS)
    yield


app = FastAPI(title="VoiceGuard Forensics", lifespan=lifespan)

PAGE_NAMES = {
    "dashboard": "Dashboard",
    "analyze-file": "Analyze File",
    "live-check": "Live Check",
    "call-monitor": "Call Monitor",
    "history": "History",
    "model-and-evaluation": "Model & Evaluation",
    "settings": "Settings",
}


@app.get("/", include_in_schema=False)
def frontend() -> RedirectResponse:
    return RedirectResponse(url="/dashboard", status_code=307)


@app.get("/login", include_in_schema=False)
def login_page() -> FileResponse:
    response = FileResponse(ROOT / "app" / "static" / "auth.html")
    response.headers["Cache-Control"] = "no-store"
    return response


@app.get("/favicon.ico", include_in_schema=False)
def favicon() -> FileResponse:
    return FileResponse(ROOT / "app" / "static" / "favicon.svg", media_type="image/svg+xml")


@app.get("/{page}", include_in_schema=False)
def page_view(page: str, request: Request) -> Response:
    if page not in PAGE_NAMES:
        raise HTTPException(status_code=404, detail="Page not found")
    if session_user(DATABASE, request.cookies.get("voiceguard_session")) is None:
        destination = quote(f"/{page}", safe="/")
        return RedirectResponse(url=f"/login?next={destination}", status_code=303)
    page_file = ROOT / "app" / "static" / "pages" / f"{page}.html"
    html = page_file.read_text(encoding="utf-8-sig")
    upload_limit_mb = max(1, (MAX_UPLOAD_BYTES + 1024 * 1024 - 1) // (1024 * 1024))
    html = html.replace("Max file size: 50 MB", f"Max file size: {upload_limit_mb} MB")
    html = html.replace("<head>", "<head><style>html{visibility:hidden}.hidden{display:none!important}</style>", 1)
    html = html.replace(
        "</head>",
        '<link rel="icon" type="image/svg+xml" href="/static/favicon.svg?v=20261019-1">'
        '<link rel="stylesheet" href="/static/account-menu.css?v=20261020-v4account1">'
        '<script>try{const savedTheme=localStorage.getItem("voiceguard.theme");if(savedTheme==="dark")document.documentElement.dataset.theme="dark"}catch{}</script></head>',
        1,
    )
    html = html.replace("</body>", '<script src="/static/account-menu.js?v=20261020-v4account1" defer></script></body>', 1)
    return HTMLResponse(html)


@app.get("/static/{asset:path}", include_in_schema=False)
def static_asset(asset: str) -> FileResponse:
    if asset == "pages" or asset.startswith("pages/"):
        raise HTTPException(status_code=404, detail="Page templates are served through authenticated routes")
    path = (ROOT / "app" / "static" / asset).resolve()
    static_root = (ROOT / "app" / "static").resolve()
    if static_root not in path.parents or not path.is_file():
        raise HTTPException(status_code=404, detail="Static asset not found")
    return FileResponse(path)


@app.get("/api/health")
def health() -> dict[str, Any]:
    def model_available(details: dict[str, Any]) -> bool:
        meta_path = details["meta"]
        if not meta_path.is_file():
            return False
        try:
            metadata = json.loads(meta_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return False
        model_path = Path(metadata["model_path"])
        if not model_path.is_absolute():
            model_path = meta_path.parent / model_path
        return model_path.is_file() and details["report"].is_file()

    profiles = {profile: model_available(details) for profile, details in MODEL_PROFILES.items()}
    legacy_meta_path = MODEL_PROFILES["legacy_for2sec"]["meta"]
    legacy_meta = {}
    if legacy_meta_path.is_file():
        try:
            legacy_meta = json.loads(legacy_meta_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            legacy_meta = {}
    model_loaded = profiles["legacy_for2sec"]
    try:
        with DATABASE.connect() as connection:
            database_ready = connection.execute("SELECT 1").fetchone() is not None
    except Exception:
        database_ready = False
    ready = model_loaded and database_ready
    return {
        "status": "ok" if ready else "degraded",
        "ready": ready,
        "database_connected": database_ready,
        "model_loaded": model_loaded,
        "model_version": legacy_meta.get("model_version"),
        "profiles": profiles,
    }


def _validate_auth_request(request: Request) -> None:
    content_type = request.headers.get("content-type", "").split(";", 1)[0].strip().lower()
    if content_type != "application/json":
        raise HTTPException(status_code=415, detail="Authentication requests must use JSON.")
    origin = request.headers.get("origin")
    if not origin:
        raise HTTPException(status_code=403, detail="A same-origin request is required.")
    try:
        parsed = urlsplit(origin)
        actual_origin = f"{parsed.scheme}://{parsed.netloc}".rstrip("/")
    except ValueError as exc:
        raise HTTPException(status_code=403, detail="A same-origin request is required.") from exc
    configured = [item.strip().rstrip("/") for item in os.getenv("ALLOWED_ORIGINS", "").split(",") if item.strip()]
    expected = configured or [f"{request.url.scheme}://{request.url.netloc}".rstrip("/")]
    if parsed.scheme not in {"http", "https"} or actual_origin not in expected:
        raise HTTPException(status_code=403, detail="A same-origin request is required.")


def _request_ip(request: Request) -> str:
    return request.client.host if request.client else "unknown"


def _require_authenticated_user(request: Request) -> dict[str, Any]:
    user = session_user(DATABASE, request.cookies.get("voiceguard_session"))
    if user is None:
        raise HTTPException(status_code=401, detail="Sign in to continue.")
    return user


def _require_ws_user(websocket: WebSocket) -> int | None:
    token = websocket.cookies.get("voiceguard_session")
    return int(user["id"]) if (user := session_user(DATABASE, token)) else None


def _issue_login(response: Response, request: Request, user: dict[str, Any]) -> dict[str, Any]:
    token = create_session(DATABASE, int(user["id"]), request.headers.get("user-agent"))
    response.set_cookie(
        "voiceguard_session", token, max_age=SESSION_SECONDS, httponly=True,
        samesite="lax",
        secure=os.getenv("VERCEL") == "1" or os.getenv("COOKIE_SECURE") == "1" or os.getenv("VOICEGUARD_COOKIE_SECURE") == "1",
        path="/",
    )
    return {"user": user}


@app.post("/api/auth/signup", status_code=201)
def auth_signup(payload: AuthPayload, request: Request, response: Response) -> dict[str, Any]:
    _validate_auth_request(request)
    ip = _request_ip(request)
    now = time.time()
    if auth_ip_attempt_count(DATABASE, ip, "signup", now - SIGNUP_WINDOW_SECONDS) >= SIGNUP_LIMIT:
        raise HTTPException(status_code=429, detail="Too many account attempts. Try again later.")
    try:
        validate_password(payload.password)
        user = create_account(DATABASE, payload.username, payload.password, payload.email, payload.display_name)
    except ValueError as exc:
        record_auth_attempt(DATABASE, payload.identity, ip, "signup", False)
        code = 409 if "already registered" in str(exc).lower() else 422
        raise HTTPException(status_code=code, detail=str(exc)) from exc
    record_auth_attempt(DATABASE, payload.identity, ip, "signup", True)
    return _issue_login(response, request, user)


@app.post("/api/auth/login")
def auth_login(payload: AuthPayload, request: Request, response: Response) -> dict[str, Any]:
    _validate_auth_request(request)
    ip = _request_ip(request)
    now = time.time()
    failures = auth_attempt_count(
        DATABASE, payload.identity, ip, "login", now - LOGIN_WINDOW_SECONDS, failures_only=True,
    )
    if failures >= LOGIN_FAILURE_LIMIT:
        raise HTTPException(status_code=429, detail="Too many sign-in attempts. Try again in 15 minutes.")
    user = verify_account(DATABASE, payload.identity, payload.password)
    if user is None:
        record_auth_attempt(DATABASE, payload.identity, ip, "login", False)
        raise HTTPException(status_code=401, detail="Invalid email or password.")
    record_auth_attempt(DATABASE, payload.identity, ip, "login", True)
    return _issue_login(response, request, user)


@app.get("/api/auth/me")
def auth_me(request: Request) -> dict[str, Any]:
    user = session_user(DATABASE, request.cookies.get("voiceguard_session"))
    return {"authenticated": user is not None, "user": user}


@app.post("/api/auth/logout")
def auth_logout(request: Request, response: Response) -> dict[str, bool]:
    _validate_auth_request(request)
    token = request.cookies.get("voiceguard_session")
    delete_session(DATABASE, token)
    response.delete_cookie(
        "voiceguard_session", path="/", httponly=True, samesite="lax",
        secure=os.getenv("VERCEL") == "1" or os.getenv("COOKIE_SECURE") == "1" or os.getenv("VOICEGUARD_COOKIE_SECURE") == "1",
    )
    return {"logged_out": True}


@app.post("/api/auth/change-password")
def auth_change_password(payload: ChangePasswordPayload, request: Request) -> dict[str, bool]:
    _validate_auth_request(request)
    user = _require_authenticated_user(request)
    identifier = user.get("email") or user.get("username") or ""
    if verify_account(DATABASE, identifier, payload.current_password) is None:
        raise HTTPException(status_code=400, detail="Current password is incorrect.")
    try:
        new_hash = hash_password(payload.new_password)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    current_token = request.cookies.get("voiceguard_session", "")
    current_hash = hashlib.sha256(current_token.encode("ascii", errors="ignore")).hexdigest()
    with DATABASE.transaction() as connection:
        connection.execute("UPDATE users SET password_hash = ?, password_salt = '' WHERE id = ?", (new_hash, user["id"]))
        connection.execute("DELETE FROM auth_sessions WHERE user_id = ? AND token_hash <> ?", (user["id"], current_hash))
    return {"password_changed": True}


@app.get("/api/account/export")
def account_export(request: Request) -> dict[str, Any]:
    user = _require_authenticated_user(request)
    with DATABASE.connect() as connection:
        rows = connection.execute("SELECT * FROM analyses WHERE user_id = ? ORDER BY created_at DESC", (user["id"],)).fetchall()
        analyses = []
        for row in rows:
            item = dict(row)
            windows = connection.execute(
                "SELECT t_start, t_end, prob, speech FROM windows WHERE analysis_id = ? ORDER BY t_start",
                (item["id"],),
            ).fetchall()
            item["windows"] = [dict(window) for window in windows]
            analyses.append(item)
        settings = connection.execute("SELECT key, value FROM settings WHERE user_id = ? ORDER BY key", (user["id"],)).fetchall()
    return {
        "format": "voiceguard-account-export-v1",
        "user": user,
        "analyses": analyses,
        "settings": {row["key"]: json.loads(row["value"]) for row in settings},
    }


@app.delete("/api/account")
def account_delete(payload: DeleteAccountPayload, request: Request, response: Response) -> dict[str, bool]:
    _validate_auth_request(request)
    user = _require_authenticated_user(request)
    identifier = user.get("email") or user.get("username") or ""
    if verify_account(DATABASE, identifier, payload.password) is None:
        raise HTTPException(status_code=400, detail="Password confirmation failed.")
    with DATABASE.transaction() as connection:
        connection.execute("DELETE FROM windows WHERE analysis_id IN (SELECT id FROM analyses WHERE user_id = ?)", (user["id"],))
        connection.execute("DELETE FROM analyses WHERE user_id = ?", (user["id"],))
        connection.execute("DELETE FROM settings WHERE user_id = ?", (user["id"],))
        connection.execute("DELETE FROM auth_sessions WHERE user_id = ?", (user["id"],))
        connection.execute("DELETE FROM ws_tickets WHERE user_id = ?", (user["id"],))
        if user.get("email"):
            connection.execute("DELETE FROM login_attempts WHERE email_lower = ?", (user["email"].casefold(),))
        if user.get("username"):
            connection.execute("DELETE FROM login_attempts WHERE email_lower = ?", (user["username"].casefold(),))
        connection.execute("DELETE FROM users WHERE id = ?", (user["id"],))
    response.delete_cookie(
        "voiceguard_session", path="/", httponly=True, samesite="lax",
        secure=os.getenv("VERCEL") == "1" or os.getenv("COOKIE_SECURE") == "1" or os.getenv("VOICEGUARD_COOKIE_SECURE") == "1",
    )
    return {"deleted": True}


@app.post("/api/auth/ws-ticket")
def auth_ws_ticket(request: Request) -> dict[str, Any]:
    _validate_auth_request(request)
    user = _require_authenticated_user(request)
    ticket = create_ws_ticket(DATABASE, int(user["id"]))
    return {"ticket": ticket, "expires_in": 60}


@app.get("/api/model/info")
def model_info(request: Request, profile: str = Query(default="legacy_for2sec")) -> dict[str, Any]:
    user = _require_authenticated_user(request)
    if profile != "legacy_for2sec":
        return profile_info(profile, int(user["id"]))
    details = MODEL_PROFILES["legacy_for2sec"]
    if not details["meta"].is_file() or not details["report"].is_file():
        raise HTTPException(status_code=503, detail="Model metadata or evaluation report is unavailable for the selected profile")
    meta_path = details["meta"]
    meta = json.loads(meta_path.read_text(encoding="utf-8"))
    settings = current_settings("legacy_for2sec", int(user["id"]))
    report = json.loads(details["report"].read_text(encoding="utf-8"))
    validation_count = report["models"]["svm"]["validation"]["count"]
    test_count = report["models"]["svm"]["test"]["count"]
    train_count = training_count("legacy_for2sec")
    model_file = meta_path.parent / meta["model_path"]
    if not model_file.is_file():
        raise HTTPException(status_code=503, detail="Model weights are unavailable for the selected profile")
    return {
        "name": meta["name"],
        "model_type": "SVM with RBF kernel and probability estimates",
        "features": "MFCC + delta + delta-delta summary",
        "feature_details": "20 coefficients with mean/std summaries (120 values total)",
        "training_dataset": meta["training_dataset"],
        "data_split": {"training": train_count, "validation": validation_count, "testing": test_count},
        "window_s": meta["window_seconds"],
        "sample_rate": meta["sample_rate"],
        "threshold": settings["threshold"],
        "uncertain_band": settings["uncertain_band"],
        "model_version": meta["model_version"],
        "model_hash": hashlib.sha256(model_file.read_bytes()).hexdigest(),
        "score_definition": meta["score_definition"],
    }


@app.get("/api/model/metrics")
def model_metrics(request: Request, profile: str = Query(default="legacy_for2sec")) -> dict[str, Any]:
    _require_authenticated_user(request)
    details = MODEL_PROFILES.get(profile)
    if details is None:
        raise HTTPException(status_code=400, detail=f"Unknown model profile: {profile}")
    report_path = details["report"]
    if not report_path.exists():
        return {"available": False}
    report = json.loads(report_path.read_text(encoding="utf-8"))
    return {"available": True, "results": report}


@app.post("/api/analyze/upload")
async def analyze_upload(
    request: Request,
    file: UploadFile = File(...),
    profile: str = Query(default="legacy_for2sec"),
) -> dict[str, Any]:
    user = _require_authenticated_user(request)
    if not file.filename:
        raise HTTPException(status_code=400, detail="A filename is required")
    if Path(file.filename).suffix.lower() not in {".wav", ".flac", ".ogg", ".mp3"}:
        raise HTTPException(status_code=415, detail="Supported formats are WAV, FLAC, OGG, and MP3")
    payload = bytearray()
    while True:
        chunk = await file.read(min(1024 * 1024, MAX_UPLOAD_BYTES + 1 - len(payload)))
        if not chunk:
            break
        payload.extend(chunk)
        if len(payload) > MAX_UPLOAD_BYTES:
            limit_mb = max(1, (MAX_UPLOAD_BYTES + 1024 * 1024 - 1) // (1024 * 1024))
            raise HTTPException(status_code=413, detail=f"Upload exceeds the {limit_mb} MB limit")
    temporary_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(suffix=Path(file.filename).suffix, delete=False) as stream:
            stream.write(payload)
            temporary_path = Path(stream.name)
        started = time.perf_counter()
        audio, sample_rate = decode_audio_file(temporary_path)
        detector = build_profile_detector(profile, int(user["id"]))
        result = detector.analyze_array(audio, sample_rate)
        latency_ms = (time.perf_counter() - started) * 1000.0
        analysis_id = save_analysis(
            DATABASE, "Upload", file.filename, result, latency_ms, profile_info(profile, int(user["id"]))["model_version"], int(user["id"])
        )
        saved = get_analysis(DATABASE, analysis_id, int(user["id"]))
        assert saved is not None
        saved["latency_ms"] = latency_ms
        return saved
    except (ValueError, OSError) as error:
        raise HTTPException(status_code=422, detail=f"Audio could not be analyzed: {error}") from error
    finally:
        if temporary_path is not None:
            temporary_path.unlink(missing_ok=True)


@app.get("/api/demo/samples")
def demo_sample_list(request: Request) -> list[dict[str, Any]]:
    _require_authenticated_user(request)
    return demo_samples()


@app.get("/api/demo/audio/{sample_id}")
def demo_audio(sample_id: str, request: Request) -> FileResponse:
    _require_authenticated_user(request)
    row = demo_row(sample_id)
    path = Path(row["path"]).resolve()
    data_root = (ROOT / "LA").resolve()
    if data_root not in path.parents or not path.is_file():
        raise HTTPException(status_code=503, detail="Demo audio file is unavailable")
    return FileResponse(path, media_type="audio/flac", filename=path.name)


@app.post("/api/demo/analyze/{sample_id}")
def analyze_demo(sample_id: str, request: Request) -> dict[str, Any]:
    user = _require_authenticated_user(request)
    row = demo_row(sample_id)
    path = Path(row["path"])
    if not path.is_file():
        raise HTTPException(status_code=503, detail="Demo audio file is unavailable")
    started = time.perf_counter()
    try:
        audio, sample_rate = decode_audio_file(path)
        settings = current_settings("asvspoof_la_balanced2500", int(user["id"]))
        result = _load_asvspoof_detector(
            str(MODEL_PROFILES["asvspoof_la_balanced2500"]["meta"]),
            float(settings["uncertain_band"]),
            float(settings["threshold"]),
        ).analyze_array(
            audio,
            sample_rate,
        )
        latency_ms = (time.perf_counter() - started) * 1000.0
        analysis_id = save_analysis(
            DATABASE,
            "Demo",
            path.name,
            result,
            latency_ms,
            "asvspoof_la_balanced2500",
            int(user["id"]),
        )
        saved = get_analysis(DATABASE, analysis_id, int(user["id"]))
        if saved is None:
            raise HTTPException(status_code=500, detail="Demo analysis was not persisted")
        saved["latency_ms"] = latency_ms
        saved["ground_truth"] = "Likely Synthetic" if row["label"] == "1" else "Likely Real"
        saved["ground_truth_label"] = int(row["label"])
        saved["attack_id"] = row["attack_id"]
        saved["demo_sample_id"] = sample_id
        return saved
    except (ValueError, OSError) as error:
        raise HTTPException(status_code=422, detail=f"Demo audio could not be analyzed: {error}") from error


@app.get("/api/dashboard/summary")
def dashboard(request: Request) -> dict[str, Any]:
    user = _require_authenticated_user(request)
    return dashboard_summary(DATABASE, int(user["id"]))


@app.get("/api/history")
def history(request: Request, source: str | None = Query(default=None), verdict: str | None = Query(default=None)) -> list[dict[str, Any]]:
    user = _require_authenticated_user(request)
    return list_analyses(DATABASE, source, verdict, int(user["id"]))


@app.get("/api/history/export.csv", response_class=PlainTextResponse)
def history_export(request: Request) -> str:
    user = _require_authenticated_user(request)
    return export_csv(DATABASE, int(user["id"]))


@app.get("/api/history/{analysis_id}")
def history_detail(analysis_id: int, request: Request) -> dict[str, Any]:
    user = _require_authenticated_user(request)
    result = get_analysis(DATABASE, analysis_id, int(user["id"]))
    if result is None:
        raise HTTPException(status_code=404, detail="Analysis not found")
    return result


@app.delete("/api/history")
def history_clear(request: Request) -> dict[str, bool]:
    user = _require_authenticated_user(request)
    clear_analyses(DATABASE, int(user["id"]))
    return {"cleared": True}


@app.get("/api/settings")
def settings_get(request: Request, profile: str = Query(default="legacy_for2sec")) -> dict[str, Any]:
    user = _require_authenticated_user(request)
    if profile not in MODEL_PROFILES:
        raise HTTPException(status_code=400, detail=f"Unknown model profile: {profile}")
    return current_settings(profile, int(user["id"]))


@app.put("/api/settings")
def settings_put(payload: SettingsPayload, request: Request, profile: str = Query(default="legacy_for2sec")) -> dict[str, Any]:
    user = _require_authenticated_user(request)
    if profile not in MODEL_PROFILES:
        raise HTTPException(status_code=400, detail=f"Unknown model profile: {profile}")
    values = payload.model_dump()
    threshold = values.pop("threshold")
    write_settings(DATABASE, values | {f"threshold:{profile}": threshold}, int(user["id"]))
    return current_settings(profile, int(user["id"]))


@app.websocket("/ws/live")
async def live_socket(websocket: WebSocket) -> None:
    await websocket.accept()
    session: StreamSession | None = None
    user_id = _require_ws_user(websocket)
    try:
        ticket_message = await websocket.receive_json()
        if ticket_message.get("type") != "auth":
            await websocket.send_json({"type": "error", "message": "Authentication required"})
            await websocket.close(code=1008)
            return
        ticket_user_id = consume_ws_ticket(DATABASE, str(ticket_message.get("ticket", "")))
        if ticket_user_id is None or (user_id is not None and ticket_user_id != user_id):
            await websocket.send_json({"type": "error", "message": "Invalid or expired WebSocket ticket"})
            await websocket.close(code=1008)
            return
        user_id = ticket_user_id
        await websocket.send_json({"type": "authenticated"})
        initial = await websocket.receive_json()
        mode = str(initial.get("mode", "mic"))
        source = str(initial.get("source", "mic"))
        if mode not in {"mic", "call"} or source not in {"mic", "system", "replay"}:
            await websocket.send_json({"type": "error", "message": "Unsupported live mode or audio source"})
            await websocket.close(code=1003)
            return
        input_sample_rate = int(initial.get("sample_rate", 0))
        if input_sample_rate <= 0 or input_sample_rate > 192000:
            await websocket.send_json({"type": "error", "message": "A valid input sample rate is required"})
            await websocket.close(code=1003)
            return
        settings = current_settings("legacy_for2sec", user_id)
        session = StreamSession(
            detector=build_detector(user_id),
            sample_rate=16000,
            mode=mode,
            source=source,
            smoothing_alpha=float(settings["smoothing_alpha"]),
            alert_consecutive_windows=int(settings["alert_consecutive_windows"]),
        )
        await websocket.send_json({"type": "status", "state": "listening"})
        while True:
            message = await websocket.receive()
            if message.get("type") == "websocket.disconnect":
                break
            if message.get("text") is not None:
                import json as _json

                control = _json.loads(message["text"])
                if control.get("type") == "stop":
                    break
                continue
            payload = message.get("bytes")
            if payload is None:
                continue
            frame = pcm16_to_float32(payload)
            if input_sample_rate != 16000:
                frame = resample_poly(frame, 16000, input_sample_rate).astype("float32", copy=False)
            for event in session.add_frame(frame):
                if event["type"] == "window":
                    status_state = "listening" if event["speech"] else "no_speech"
                    await websocket.send_json({"type": "status", "state": status_state})
                    if float(event["latency_ms"]) > float(settings["hop_seconds"]) * 1000.0:
                        await websocket.send_json({"type": "status", "state": "lagging"})
                await websocket.send_json(event)
        for event in session.flush():
            if event["type"] == "window":
                status_state = "listening" if event["speech"] else "no_speech"
                await websocket.send_json({"type": "status", "state": status_state})
            await websocket.send_json(event)
        summary = _save_stream_session(session, user_id)
        await websocket.send_json(summary)
    except WebSocketDisconnect:
        if session is not None and session.total_samples_received:
            session.flush()
            if user_id is not None:
                _save_stream_session(session, user_id, partial=True)
        return


def _save_stream_session(session: StreamSession, user_id: int, partial: bool = False) -> dict[str, Any]:
    summary = session.summary()
    if partial:
        summary["partial"] = True
    analysis_id = save_analysis(
        DATABASE,
        session.source,
        f"{session.mode} session",
        summary,
        float(summary["latency_ms"]),
        "classical_for_2sec",
        user_id,
    )
    summary["session_id"] = analysis_id
    return summary

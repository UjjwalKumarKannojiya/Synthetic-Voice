from __future__ import annotations

import io
import wave

import numpy as np
import pytest
from fastapi.testclient import TestClient

import app.main as main
from app.db.database import Database


ORIGIN = {"Origin": "http://testserver"}


def _signup(client: TestClient, address: str) -> None:
    response = client.post(
        "/api/auth/signup",
        json={"email": address, "password": "Authorization-Test-77"},
        headers=ORIGIN,
    )
    assert response.status_code == 201, response.text


def _wav() -> bytes:
    samples = (0.1 * np.sin(2 * np.pi * 220 * np.arange(32000) / 16000) * 32767).astype("<i2")
    output = io.BytesIO()
    with wave.open(output, "wb") as stream:
        stream.setnchannels(1)
        stream.setsampwidth(2)
        stream.setframerate(16000)
        stream.writeframes(samples.tobytes())
    return output.getvalue()


def test_data_requires_account_and_isolated_between_users(tmp_path, monkeypatch):
    database = Database(tmp_path / "isolation.sqlite3")
    monkeypatch.setattr(main, "DATABASE", database)
    with TestClient(main.app) as alice, TestClient(main.app) as bob:
        assert alice.get("/api/history").status_code == 401
        _signup(alice, "alice@example.test")
        _signup(bob, "bob@example.test")

        upload = alice.post("/api/analyze/upload", files={"file": ("voice.wav", _wav(), "audio/wav")})
        assert upload.status_code == 200, upload.text
        analysis_id = upload.json()["id"]
        assert len(alice.get("/api/history").json()) == 1
        assert bob.get("/api/history").json() == []
        assert bob.get("/api/dashboard/summary").json()["total"] == 0
        assert bob.get(f"/api/history/{analysis_id}").status_code == 404
        assert bob.get("/api/account/export").json()["analyses"] == []

        alice_settings = alice.get("/api/settings").json()
        assert alice.put("/api/settings", json=alice_settings | {"threshold": 0.2}).status_code == 200
        assert bob.get("/api/settings").json()["threshold"] != 0.2
        assert bob.delete("/api/history").status_code == 200
        assert len(alice.get("/api/history").json()) == 1


def test_websocket_requires_single_use_ticket_and_ticket_owner(tmp_path, monkeypatch):
    database = Database(tmp_path / "tickets.sqlite3")
    monkeypatch.setattr(main, "DATABASE", database)
    with TestClient(main.app) as alice, TestClient(main.app) as bob:
        _signup(alice, "ticket-alice@example.test")
        _signup(bob, "ticket-bob@example.test")
        ticket = alice.post("/api/auth/ws-ticket", json={}, headers=ORIGIN).json()["ticket"]
        with bob.websocket_connect("/ws/live") as websocket:
            websocket.send_json({"type": "auth", "ticket": ticket})
            assert websocket.receive_json()["type"] == "error"
        with alice.websocket_connect("/ws/live") as websocket:
            websocket.send_json({"type": "auth", "ticket": ticket})
            assert websocket.receive_json()["type"] == "error"
        with alice.websocket_connect("/ws/live") as websocket:
            websocket.send_json({"type": "auth", "ticket": "invalid"})
            assert websocket.receive_json()["type"] == "error"


@pytest.mark.parametrize("page", ["dashboard", "analyze-file", "live-check", "call-monitor", "history", "model-and-evaluation", "settings"])
def test_private_pages_redirect_to_login_and_keep_safe_return_target(tmp_path, monkeypatch, page):
    monkeypatch.setattr(main, "DATABASE", Database(tmp_path / "page-guard.sqlite3"))
    with TestClient(main.app) as client:
        response = client.get(f"/{page}", follow_redirects=False)
        assert response.status_code == 303
        assert response.headers["location"] == f"/login?next=/{page}"
        login_page = client.get(response.headers["location"])
        assert login_page.status_code == 200
        assert 'name="identity"' in login_page.text
        assert 'name="display_name"' in login_page.text
        assert "/static/auth-page.js?v=20261020-v4account1" in login_page.text
        signup = client.post(
            "/api/auth/signup",
            json={"email": "page-user@example.test", "display_name": "Page User", "password": "Page-User-Password-72"},
            headers=ORIGIN,
        )
        assert signup.status_code == 201
        assert client.get(f"/{page}").status_code == 200

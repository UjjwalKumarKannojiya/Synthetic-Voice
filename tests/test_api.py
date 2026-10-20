import io
import wave
from contextlib import contextmanager

import numpy as np
from fastapi.testclient import TestClient

from app.main import app


@contextmanager
def authenticated_client():
    with TestClient(app) as client:
        response = client.post(
            "/api/auth/signup",
            json={"email": "api-user@example.test", "password": "Api-Test-Password-71"},
            headers={"Origin": "http://testserver"},
        )
        assert response.status_code == 201, response.text
        yield client


def pcm16_bytes(amplitude: float = 0.15, duration_seconds: float = 2.0) -> bytes:
    sample_count = round(16000 * duration_seconds)
    samples = (
        amplitude
        * np.sin(2.0 * np.pi * 220.0 * np.arange(sample_count) / 16000.0)
        * 32767
    ).astype("<i2")
    return samples.tobytes()


def wav_bytes(amplitude: float = 0.15, duration_seconds: float = 2.0) -> bytes:
    output = io.BytesIO()
    with wave.open(output, "wb") as stream:
        stream.setnchannels(1)
        stream.setsampwidth(2)
        stream.setframerate(16000)
        stream.writeframes(pcm16_bytes(amplitude, duration_seconds))
    return output.getvalue()


def test_api_contract_and_upload(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr("app.main.DATABASE", __import__("app.db.database", fromlist=["Database"]).Database(tmp_path / "test.sqlite3"))
    with authenticated_client() as client:
        health = client.get("/api/health")
        assert health.status_code == 200
        assert health.json()["model_loaded"] is True

        response = client.post(
            "/api/analyze/upload",
            files={"file": ("sample.wav", wav_bytes(), "audio/wav")},
        )
        assert response.status_code == 200, response.text
        analysis = response.json()
        assert analysis["id"] > 0
        assert analysis["sample_rate"] == 16000
        assert len(analysis["windows"]) == 1

        history = client.get("/api/history")
        assert history.status_code == 200
        assert len(history.json()) == 1
        assert client.get(f"/api/history/{analysis['id']}").json()["id"] == analysis["id"]
        assert client.get("/api/dashboard/summary").json()["total"] == 1
        assert "created_at" in client.get("/api/history/export.csv").text


def test_settings_round_trip_and_clear(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr("app.main.DATABASE", __import__("app.db.database", fromlist=["Database"]).Database(tmp_path / "test.sqlite3"))
    with authenticated_client() as client:
        current = client.get("/api/settings").json()
        assert current["threshold"] == client.get("/api/model/info").json()["threshold"]
        assert client.put("/api/settings", json=current | {"hop_seconds": 0.000001}).status_code == 422
        payload = current | {"threshold": 0.41, "uncertain_band": 0.1}
        response = client.put("/api/settings", json=payload)
        assert response.status_code == 200
        assert response.json()["threshold"] == 0.41
        assert response.json()["uncertain_band"] == 0.1
        asvspoof = client.get("/api/settings?profile=asvspoof_la_balanced2500").json()
        assert asvspoof["threshold"] == client.get("/api/model/info?profile=asvspoof_la_balanced2500").json()["threshold"]
        assert "store_raw_audio" not in response.json()
        assert client.delete("/api/history").json() == {"cleared": True}
        assert client.get("/api/history").json() == []


def test_asvspoof_profile_is_explicit_and_persisted(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr("app.main.DATABASE", __import__("app.db.database", fromlist=["Database"]).Database(tmp_path / "test.sqlite3"))
    with authenticated_client() as client:
        info = client.get("/api/model/info?profile=asvspoof_la_balanced2500")
        assert info.status_code == 200
        assert info.json()["training_dataset"] == "ASVspoof2019_LA"
        response = client.post(
            "/api/analyze/upload?profile=asvspoof_la_balanced2500",
            files={"file": ("sample.wav", wav_bytes(), "audio/wav")},
        )
        assert response.status_code == 200, response.text
        analysis = response.json()
        assert analysis["model_version"].startswith("asvspoof_la_")
        assert client.get(f"/api/history/{analysis['id']}").json()["model_version"] == analysis["model_version"]


def test_unknown_model_profile_is_rejected(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr("app.main.DATABASE", __import__("app.db.database", fromlist=["Database"]).Database(tmp_path / "test.sqlite3"))
    with authenticated_client() as client:
        assert client.get("/api/model/info?profile=unknown").status_code == 400
        assert client.post(
            "/api/analyze/upload?profile=unknown",
            files={"file": ("sample.wav", wav_bytes(), "audio/wav")},
        ).status_code == 400


def test_vercel_upload_limit_is_disclosed_and_enforced(tmp_path, monkeypatch) -> None:
    from app.db.database import Database

    monkeypatch.setattr("app.main.DATABASE", Database(tmp_path / "test.sqlite3"))
    monkeypatch.setattr("app.main.MAX_UPLOAD_BYTES", 4 * 1024 * 1024)
    with authenticated_client() as client:
        page = client.get("/analyze-file")
        assert "Max file size: 4 MB" in page.text
        response = client.post(
            "/api/analyze/upload",
            files={"file": ("oversized.wav", b"x" * (4 * 1024 * 1024 + 1), "audio/wav")},
        )
        assert response.status_code == 413
        assert response.json()["detail"] == "Upload exceeds the 4 MB limit"


def test_demo_listing_hides_truth_and_analysis_reveals_it(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr("app.main.DATABASE", __import__("app.db.database", fromlist=["Database"]).Database(tmp_path / "test.sqlite3"))
    with authenticated_client() as client:
        response = client.get("/api/demo/samples")
        assert response.status_code == 200
        sample = response.json()[0]
        assert {"id", "name", "duration_s"} == set(sample)
        assert "label" not in sample
        result = client.post(f"/api/demo/analyze/{sample['id']}")
        assert result.status_code == 200, result.text
        payload = result.json()
        assert payload["source"] == "Demo"
        assert payload["ground_truth_label"] in {0, 1}
        assert payload["attack_id"] == "-"


def test_live_websocket_returns_window_and_summary(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr("app.main.DATABASE", __import__("app.db.database", fromlist=["Database"]).Database(tmp_path / "test.sqlite3"))
    with authenticated_client() as client:
        with client.websocket_connect("/ws/live") as websocket:
            ticket = client.post("/api/auth/ws-ticket", json={}, headers={"Origin": "http://testserver"}).json()["ticket"]
            websocket.send_json({"type": "auth", "ticket": ticket})
            assert websocket.receive_json()["type"] == "authenticated"
            websocket.send_json({"mode": "mic", "source": "mic", "sample_rate": 16000})
            status = websocket.receive_json()
            while status.get("type") != "status":
                status = websocket.receive_json()
            assert status["state"] == "listening"
            websocket.send_bytes(wav_bytes())
            event = websocket.receive_json()
            while event["type"] != "window":
                event = websocket.receive_json()
            window = event
            settings = client.get("/api/settings").json()
            assert window["threshold"] == settings["threshold"]
            assert window["uncertain_band"] == settings["uncertain_band"]
            websocket.send_json({"type": "stop"})
            summary = websocket.receive_json()
            assert summary["type"] == "summary"
            assert summary["session_id"] > 0
            assert summary["duration_s"] >= 2.0
            assert summary["latency_ms"] >= 0.0


def test_live_websocket_flushes_a_short_audio_tail_on_stop(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr("app.main.DATABASE", __import__("app.db.database", fromlist=["Database"]).Database(tmp_path / "test.sqlite3"))
    with authenticated_client() as client:
        with client.websocket_connect("/ws/live") as websocket:
            ticket = client.post("/api/auth/ws-ticket", json={}, headers={"Origin": "http://testserver"}).json()["ticket"]
            websocket.send_json({"type": "auth", "ticket": ticket})
            assert websocket.receive_json()["type"] == "authenticated"
            websocket.send_json({"mode": "mic", "source": "mic", "sample_rate": 16000})
            status = websocket.receive_json()
            while status.get("type") != "status":
                status = websocket.receive_json()

            websocket.send_bytes(pcm16_bytes(duration_seconds=1.5))
            websocket.send_json({"type": "stop"})
            event = websocket.receive_json()
            while event.get("type") != "window":
                event = websocket.receive_json()
            assert event["speech"] is True
            assert event["prob"] is not None

            summary = websocket.receive_json()
            assert summary["type"] == "summary"
            assert summary["duration_s"] >= 1.5
            assert summary["mean_prob"] is not None
            assert summary["windows"]


def test_frontend_and_profile_metrics_are_real_routes(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(
        "app.main.DATABASE",
        __import__("app.db.database", fromlist=["Database"]).Database(tmp_path / "test.sqlite3"),
    )
    with authenticated_client() as client:
        root = client.get("/", follow_redirects=False)
        assert root.status_code == 307
        assert root.headers["location"] == "/dashboard"
        page_route = client.get("/dashboard")
        assert page_route.status_code == 200
        assert "Forensic Dashboard" in page_route.text
        assert "/static/app-runtime.js" in page_route.text
        assert client.get("/live-check").status_code == 200
        assert client.get("/call-monitor").status_code == 200
        assert client.get("/static/pages/dashboard.html").status_code == 404
        assert client.get("/api/model/metrics?profile=asvspoof_la_balanced2500").json()["results"]["test"]["count"] > 0


def test_model_threshold_is_applied_to_following_upload_only(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr("app.main.DATABASE", __import__("app.db.database", fromlist=["Database"]).Database(tmp_path / "test.sqlite3"))
    with authenticated_client() as client:
        original = client.get("/api/settings").json()
        changed = original | {"threshold": 0.0, "uncertain_band": 0.0}
        assert client.put("/api/settings", json=changed).status_code == 200
        response = client.post(
            "/api/analyze/upload",
            files={"file": ("sample.wav", wav_bytes(), "audio/wav")},
        )
        assert response.status_code == 200, response.text
        first = response.json()
        assert first["threshold"] == 0.0
        assert first["verdict"] == "Likely Synthetic"
        assert client.put("/api/settings", json=original | {"threshold": 1.0, "uncertain_band": 0.0}).status_code == 200
        second = client.post(
            "/api/analyze/upload",
            files={"file": ("sample.wav", wav_bytes(), "audio/wav")},
        ).json()
        assert first["threshold"] == 0.0
        assert second["threshold"] == 1.0
        assert first["id"] != second["id"]


def _validation_rows() -> dict[int, dict[str, str]]:
    import csv
    from pathlib import Path

    manifest = Path(__file__).resolve().parents[1] / "data" / "manifests" / "for_2sec.csv"
    selected = {}
    with manifest.open(encoding="utf-8", newline="") as stream:
        for row in csv.DictReader(stream):
            if row["split"] == "validation" and int(row["label"]) not in selected:
                selected[int(row["label"])] = row
            if len(selected) == 2:
                break
    return selected


def test_real_and_fake_validation_uploads_use_audio_and_update_history(tmp_path, monkeypatch) -> None:
    from pathlib import Path

    database = __import__("app.db.database", fromlist=["Database"]).Database(tmp_path / "test.sqlite3")
    monkeypatch.setattr("app.main.DATABASE", database)
    rows = _validation_rows()
    assert set(rows) == {0, 1}
    with authenticated_client() as client:
        outcomes = {}
        for label, row in rows.items():
            path = Path(row["path"])
            response = client.post(
                "/api/analyze/upload",
                files={"file": (path.name, path.read_bytes(), "audio/wav")},
            )
            assert response.status_code == 200, response.text
            result = response.json()
            outcomes[label] = result
            assert result["duration_s"] == float(row["duration_seconds"])
            assert len(result["windows"]) > 0
        assert outcomes[0]["mean_prob"] != outcomes[1]["mean_prob"]
        assert len(client.get("/api/history").json()) == 2


def test_repeated_upload_is_deterministic_and_saved_twice(tmp_path, monkeypatch) -> None:
    from pathlib import Path

    monkeypatch.setattr(
        "app.main.DATABASE",
        __import__("app.db.database", fromlist=["Database"]).Database(tmp_path / "test.sqlite3"),
    )
    row = _validation_rows()[0]
    path = Path(row["path"])
    with authenticated_client() as client:
        results = [
            client.post(
                "/api/analyze/upload",
                files={"file": (path.name, path.read_bytes(), "audio/wav")},
            ).json()
            for _ in range(2)
        ]
        assert results[0]["mean_prob"] == results[1]["mean_prob"]
        assert results[0]["id"] != results[1]["id"]
        assert len(client.get("/api/history").json()) == 2


def test_direct_database_insert_is_visible_to_dashboard_and_history(tmp_path, monkeypatch) -> None:
    from app.db.crud import save_analysis
    from app.db.database import Database

    database = Database(tmp_path / "test.sqlite3")
    monkeypatch.setattr("app.main.DATABASE", database)
    database.initialize()
    result = {
        "duration_s": 2.0, "sample_rate": 16000, "mean_prob": 0.25, "max_prob": 0.25,
        "verdict": "Likely Real", "speech_ratio": 1.0, "threshold": 0.5,
        "uncertain_band": 0.05, "windows": [{"t_start": 0.0, "t_end": 2.0, "prob": 0.25, "speech": True}],
    }
    with authenticated_client() as client:
        user_id = client.get("/api/auth/me").json()["user"]["id"]
        row_id = save_analysis(database, "Upload", "direct-row.wav", result, 4.0, "test-model", user_id)
        assert client.get("/api/dashboard/summary").json()["total"] == 1
        history = client.get("/api/history").json()
        assert len(history) == 1
        assert history[0]["id"] == row_id

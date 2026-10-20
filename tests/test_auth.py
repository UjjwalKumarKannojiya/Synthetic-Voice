from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

import app.main as main
from app.core.auth import consume_ws_ticket
from app.db.database import Database


ORIGIN = {"Origin": "http://testserver"}
NEW_ACCOUNT = {"email": "user@example.test", "display_name": "Test User", "password": "Long-Unique-Pass-42"}


@pytest.fixture
def auth_client(tmp_path, monkeypatch):
    database = Database(tmp_path / "auth.sqlite3")
    monkeypatch.setattr(main, "DATABASE", database)
    with TestClient(main.app) as client:
        yield client, database
    database.dispose()


def signup(client: TestClient, payload: dict | None = None):
    return client.post("/api/auth/signup", json=payload or NEW_ACCOUNT, headers=ORIGIN)


def test_signup_uses_argon2id_and_opaque_lax_httponly_session(auth_client):
    client, database = auth_client
    response = signup(client)
    assert response.status_code == 201, response.text
    cookie = response.headers["set-cookie"].lower()
    assert "httponly" in cookie and "samesite=lax" in cookie
    assert client.get("/api/auth/me").json()["authenticated"] is True
    with database.connect() as connection:
        row = connection.execute("SELECT password_hash, password_salt FROM users").fetchone()
        assert row["password_hash"].startswith("$argon2id$")
        assert row["password_salt"] in (None, "")
        assert NEW_ACCOUNT["password"] not in str(dict(row))


def test_email_signup_supports_legacy_not_null_username_schema(tmp_path):
    database = Database(tmp_path / "legacy-users.sqlite3")
    with database.connect() as connection:
        connection.execute(
            "CREATE TABLE users (id INTEGER PRIMARY KEY, username TEXT NOT NULL UNIQUE, "
            "email TEXT UNIQUE, display_name TEXT, password_salt TEXT NOT NULL, password_hash TEXT NOT NULL, "
            "is_active INTEGER NOT NULL DEFAULT 1, email_verified INTEGER NOT NULL DEFAULT 0, "
            "created_at TEXT NOT NULL, last_login_at TEXT)"
        )
    created = main.create_account(database, None, "Legacy-Email-Password-77", "legacy@example.test")
    assert created["email"] == "legacy@example.test"
    assert created["username"].startswith("acct_")
    with pytest.raises(ValueError, match="already registered"):
        main.create_account(database, None, "Legacy-Email-Password-77", "legacy@example.test")


def test_login_errors_are_generic_and_duplicate_signup_is_rejected(auth_client):
    client, _ = auth_client
    assert signup(client).status_code == 201
    duplicate = signup(client)
    assert duplicate.status_code == 409
    unknown = client.post(
        "/api/auth/login", json={"email": "nobody@example.test", "password": NEW_ACCOUNT["password"]},
        headers=ORIGIN | {"X-Forwarded-For": "192.0.2.10"},
    )
    wrong = client.post(
        "/api/auth/login", json={"email": NEW_ACCOUNT["email"], "password": "Wrong-Password-Value"},
        headers=ORIGIN | {"X-Forwarded-For": "192.0.2.11"},
    )
    assert (unknown.status_code, unknown.json()["detail"]) == (wrong.status_code, wrong.json()["detail"])
    assert unknown.status_code == 401


def test_login_rate_limit_is_database_backed(auth_client):
    client, database = auth_client
    assert signup(client).status_code == 201
    for _ in range(5):
        response = client.post(
            "/api/auth/login", json={"email": NEW_ACCOUNT["email"], "password": "Wrong-Password-Value"},
            headers=ORIGIN,
        )
        assert response.status_code == 401
    locked = client.post(
        "/api/auth/login", json={"email": NEW_ACCOUNT["email"], "password": NEW_ACCOUNT["password"]},
        headers=ORIGIN,
    )
    assert locked.status_code == 429
    with database.connect() as connection:
        assert connection.execute("SELECT COUNT(*) FROM login_attempts WHERE action='login' AND success=0").fetchone()[0] == 5


def test_auth_csrf_origin_and_json_content_type(auth_client):
    client, _ = auth_client
    missing_origin = client.post("/api/auth/signup", json=NEW_ACCOUNT)
    wrong_origin = client.post("/api/auth/signup", json=NEW_ACCOUNT, headers={"Origin": "https://attacker.invalid"})
    assert missing_origin.status_code == 403
    assert wrong_origin.status_code == 403
    assert client.post(
        "/api/auth/signup", content='{"email":"a@b.test"}',
        headers={"Origin": "http://testserver", "Content-Type": "text/plain"},
    ).status_code in {403, 415, 422}


def test_common_password_is_rejected_and_production_cookie_is_secure(auth_client, monkeypatch):
    client, _ = auth_client
    weak = signup(client, {"email": "weak@example.test", "password": "password123"})
    assert weak.status_code == 422
    monkeypatch.setenv("VERCEL", "1")
    response = signup(client, {"email": "secure@example.test", "password": "Strong-Unique-Pass-57"})
    assert response.status_code == 201
    assert "secure" in response.headers["set-cookie"].lower()


def test_signup_ip_rate_limit_is_database_backed(auth_client):
    client, database = auth_client
    for index in range(10):
        response = signup(client, {"email": f"user{index}@example.test", "password": "Strong-Unique-Pass-57"})
        assert response.status_code == 201
    blocked = signup(client, {"email": "eleventh@example.test", "password": "Strong-Unique-Pass-57"})
    assert blocked.status_code == 429
    with database.connect() as connection:
        assert connection.execute("SELECT COUNT(*) FROM login_attempts WHERE action='signup' AND success=1").fetchone()[0] == 10


def test_session_logout_expiry_password_change_and_ws_ticket(auth_client):
    client, database = auth_client
    assert signup(client).status_code == 201
    ticket_response = client.post("/api/auth/ws-ticket", json={}, headers=ORIGIN)
    assert ticket_response.status_code == 200
    ticket = ticket_response.json()["ticket"]
    user_id = consume_ws_ticket(database, ticket)
    assert user_id is not None
    assert consume_ws_ticket(database, ticket) is None
    changed = client.post(
        "/api/auth/change-password",
        json={"current_password": NEW_ACCOUNT["password"], "new_password": "Another-Unique-Pass-91"},
        headers=ORIGIN,
    )
    assert changed.status_code == 200
    assert client.get("/api/auth/me").json()["authenticated"] is True
    old_login = client.post(
        "/api/auth/login", json={"email": NEW_ACCOUNT["email"], "password": NEW_ACCOUNT["password"]},
        headers=ORIGIN | {"X-Forwarded-For": "192.0.2.20"},
    )
    new_login = client.post(
        "/api/auth/login", json={"email": NEW_ACCOUNT["email"], "password": "Another-Unique-Pass-91"},
        headers=ORIGIN | {"X-Forwarded-For": "192.0.2.21"},
    )
    assert old_login.status_code == 401
    assert new_login.status_code == 200
    client.post("/api/auth/logout", json={}, headers=ORIGIN)
    assert client.get("/api/auth/me").json()["authenticated"] is False

    # Use a fresh session and expire it in the database to prove expiry is enforced server-side.
    assert client.post(
        "/api/auth/login", json={"email": NEW_ACCOUNT["email"], "password": "Another-Unique-Pass-91"},
        headers=ORIGIN,
    ).status_code == 200
    token = client.cookies.get("voiceguard_session")
    with database.connect() as connection:
        import hashlib
        token_hash = hashlib.sha256(token.encode("ascii")).hexdigest()
        connection.execute("UPDATE auth_sessions SET expires_at=0 WHERE token_hash=?", (token_hash,))
    assert client.get("/api/auth/me").json()["authenticated"] is False


def test_account_export_and_deletion_remove_only_owned_rows(auth_client):
    client, database = auth_client
    response = signup(client)
    assert response.status_code == 201
    user_id = response.json()["user"]["id"]
    with database.connect() as connection:
        connection.execute(
            "INSERT INTO analyses(user_id,created_at,source,name,duration_s,sample_rate,mean_prob,max_prob,verdict,speech_ratio,latency_ms,model_version,threshold,band) "
            "VALUES(?, 'now', 'mic', 'owned', 1, 16000, 0.2, 0.2, 'Likely Real', 1, 2, 'test', 0.5, 0.05)",
            (user_id,),
        )
        connection.execute("INSERT INTO settings(user_id,key,value) VALUES(?,?,?)", (user_id, "threshold", "0.5"))
    exported = client.get("/api/account/export")
    assert exported.status_code == 200
    assert len(exported.json()["analyses"]) == 1
    assert exported.json()["settings"] == {"threshold": 0.5}
    rejected = client.request("DELETE", "/api/account", json={"password": "not-the-password"}, headers=ORIGIN)
    assert rejected.status_code == 400
    deleted = client.request("DELETE", "/api/account", json={"password": NEW_ACCOUNT["password"]}, headers=ORIGIN)
    assert deleted.status_code == 200
    assert client.get("/api/auth/me").json()["authenticated"] is False
    with database.connect() as connection:
        assert connection.execute("SELECT COUNT(*) FROM users").fetchone()[0] == 0
        assert connection.execute("SELECT COUNT(*) FROM analyses WHERE user_id=?", (user_id,)).fetchone()[0] == 0
        assert connection.execute("SELECT COUNT(*) FROM settings WHERE user_id=?", (user_id,)).fetchone()[0] == 0


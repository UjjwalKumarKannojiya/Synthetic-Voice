"""Password, account, rate-limit and opaque-cookie session helpers."""

from __future__ import annotations

import hashlib
import hmac
import secrets
from datetime import datetime, timedelta, timezone
from typing import Any

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError, VerifyMismatchError
from sqlalchemy.exc import IntegrityError

from ..db.database import Database


SESSION_SECONDS = 7 * 24 * 60 * 60
LOGIN_WINDOW_SECONDS = 15 * 60
LOGIN_FAILURE_LIMIT = 5
SIGNUP_WINDOW_SECONDS = 60 * 60
SIGNUP_LIMIT = 10
COMMON_PASSWORDS = {
    "password123", "password1234", "1234567890", "qwerty12345", "letmein123", "admin12345",
}
_PASSWORD_HASHER = PasswordHasher()
_DUMMY_PASSWORD_HASH = _PASSWORD_HASHER.hash(secrets.token_urlsafe(32))


def _dummy_password_verify(password: str) -> None:
    try:
        _PASSWORD_HASHER.verify(_DUMMY_PASSWORD_HASH, password)
    except (VerifyMismatchError, VerificationError, InvalidHashError):
        pass


def validate_password(password: str) -> None:
    if len(password) < 10 or len(password) > 128:
        raise ValueError("Password must be between 10 and 128 characters.")
    if password.casefold() in COMMON_PASSWORDS:
        raise ValueError("Choose a less common password.")


def hash_password(password: str) -> str:
    validate_password(password)
    return _PASSWORD_HASHER.hash(password)


def _password_hash(password: str, salt: bytes) -> bytes:
    """Verify legacy PBKDF2 hashes only; new credentials use Argon2id."""
    return hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, 310_000)


def _public_user(row: Any) -> dict[str, Any]:
    return {
        "id": int(row["id"]),
        "username": row["username"],
        "email": row["email"],
        "display_name": row["display_name"],
        "created_at": str(row["created_at"]),
    }


def create_account(
    database: Database,
    username: str | None,
    password: str,
    email: str | None = None,
    display_name: str | None = None,
) -> dict[str, Any]:
    validate_password(password)
    clean_username = username.strip() if username and username.strip() else None
    clean_email = email.strip().casefold() if email and email.strip() else None
    if not clean_username and not clean_email:
        raise ValueError("An email address is required.")
    if clean_username is None:
        # Older local SQLite databases require a username column value even for email accounts.
        # Keep this generated identifier internal; the user signs in with their email address.
        clean_username = f"acct_{secrets.token_hex(12)}"
    if clean_email and ("@" not in clean_email or len(clean_email) > 320):
        raise ValueError("Enter a valid email address.")
    clean_name = display_name.strip()[:120] if display_name and display_name.strip() else None
    created_at = datetime.now(timezone.utc).isoformat()
    encoded_hash = hash_password(password)
    try:
        with database.connect() as connection:
            cursor = connection.execute(
                "INSERT INTO users(username, email, display_name, password_salt, password_hash, created_at) "
                "VALUES (?, ?, ?, ?, ?, ?) RETURNING id",
                (clean_username, clean_email, clean_name, "", encoded_hash, created_at),
            )
            row = connection.execute("SELECT * FROM users WHERE id = ?", (cursor.lastrowid,)).fetchone()
            return _public_user(row)
    except IntegrityError as exc:
        reason = str(exc.orig).casefold()
        if "unique constraint" in reason or "duplicate key" in reason:
            raise ValueError("That account is already registered.") from exc
        raise


def verify_account(database: Database, identifier: str, password: str) -> dict[str, Any] | None:
    clean_identifier = identifier.strip()
    if "@" in clean_identifier:
        query = "SELECT * FROM users WHERE lower(email) = lower(?)"
    else:
        query = "SELECT * FROM users WHERE username = ? COLLATE NOCASE"
    with database.connect() as connection:
        row = connection.execute(query, (clean_identifier,)).fetchone()
    if row is None or not row["is_active"]:
        _dummy_password_verify(password)
        return None
    stored_hash = str(row["password_hash"])
    if stored_hash.startswith("$argon2id$"):
        try:
            valid = _PASSWORD_HASHER.verify(stored_hash, password)
        except (VerifyMismatchError, VerificationError, InvalidHashError):
            return None
        if valid and _PASSWORD_HASHER.check_needs_rehash(stored_hash):
            with database.connect() as connection:
                connection.execute("UPDATE users SET password_hash = ? WHERE id = ?", (_PASSWORD_HASHER.hash(password), row["id"]))
    else:
        # Upgrade existing salted PBKDF2 records after a successful login.
        salt_hex = row["password_salt"]
        if not salt_hex:
            return None
        actual = _password_hash(password, bytes.fromhex(salt_hex))
        expected = bytes.fromhex(stored_hash)
        valid = hmac.compare_digest(actual, expected)
        if valid:
            with database.connect() as connection:
                connection.execute(
                    "UPDATE users SET password_hash = ?, password_salt = '' WHERE id = ?",
                    (_PASSWORD_HASHER.hash(password), row["id"]),
                )
        else:
            _dummy_password_verify(password)
    if not valid:
        return None
    with database.connect() as connection:
        connection.execute("UPDATE users SET last_login_at = ? WHERE id = ?", (datetime.now(timezone.utc).isoformat(), row["id"]))
    return _public_user(row)


def record_auth_attempt(database: Database, identifier: str, ip: str, action: str, success: bool) -> None:
    now = datetime.now(timezone.utc).timestamp()
    with database.connect() as connection:
        connection.execute(
            "INSERT INTO login_attempts(email_lower, ip, action, success, created_at) VALUES (?, ?, ?, ?, ?)",
            (identifier.strip().casefold()[:320], ip[:64], action, success, now),
        )
        connection.execute(
            "DELETE FROM login_attempts WHERE created_at < ?",
            (now - max(LOGIN_WINDOW_SECONDS, SIGNUP_WINDOW_SECONDS) * 2,),
        )


def auth_attempt_count(database: Database, identifier: str, ip: str, action: str, since: float, failures_only: bool = False) -> int:
    query = "SELECT COUNT(*) FROM login_attempts WHERE action = ? AND created_at >= ? AND ip = ? AND email_lower = ?"
    params: tuple[Any, ...] = (action, since, ip[:64], identifier.strip().casefold()[:320])
    if failures_only:
        query += " AND success = false"
    with database.connect() as connection:
        return int(connection.execute(query, params).fetchone()[0])


def auth_ip_attempt_count(database: Database, ip: str, action: str, since: float) -> int:
    with database.connect() as connection:
        return int(connection.execute(
            "SELECT COUNT(*) FROM login_attempts WHERE action = ? AND created_at >= ? AND ip = ?",
            (action, since, ip[:64]),
        ).fetchone()[0])


def create_session(database: Database, user_id: int, user_agent: str | None = None) -> str:
    token = secrets.token_urlsafe(32)
    token_hash = hashlib.sha256(token.encode("ascii")).hexdigest()
    now = datetime.now(timezone.utc)
    with database.connect() as connection:
        connection.execute("DELETE FROM auth_sessions WHERE expires_at <= ? OR revoked_at IS NOT NULL", (now.timestamp(),))
        connection.execute(
            "INSERT INTO auth_sessions(token_hash, user_id, created_at, expires_at, revoked_at, user_agent) "
            "VALUES (?, ?, ?, ?, NULL, ?)",
            (token_hash, user_id, now.isoformat(), (now + timedelta(seconds=SESSION_SECONDS)).timestamp(), (user_agent or "")[:512]),
        )
    return token


def session_user(database: Database, token: str | None) -> dict[str, Any] | None:
    if not token:
        return None
    token_hash = hashlib.sha256(token.encode("ascii", errors="ignore")).hexdigest()
    now = datetime.now(timezone.utc).timestamp()
    with database.connect() as connection:
        row = connection.execute(
            "SELECT users.* FROM auth_sessions JOIN users ON users.id = auth_sessions.user_id "
            "WHERE auth_sessions.token_hash = ? AND auth_sessions.expires_at > ? "
            "AND auth_sessions.revoked_at IS NULL AND users.is_active = true",
            (token_hash, now),
        ).fetchone()
    return _public_user(row) if row else None


def delete_session(database: Database, token: str | None) -> None:
    if not token:
        return
    token_hash = hashlib.sha256(token.encode("ascii", errors="ignore")).hexdigest()
    with database.connect() as connection:
        connection.execute("DELETE FROM auth_sessions WHERE token_hash = ?", (token_hash,))


def create_ws_ticket(database: Database, user_id: int) -> str:
    ticket = secrets.token_urlsafe(32)
    ticket_hash = hashlib.sha256(ticket.encode("ascii")).hexdigest()
    now = datetime.now(timezone.utc).timestamp()
    with database.connect() as connection:
        connection.execute("DELETE FROM ws_tickets WHERE expires_at <= ? OR used_at IS NOT NULL", (now,))
        connection.execute(
            "INSERT INTO ws_tickets(user_id, ticket_hash, expires_at, used_at) VALUES (?, ?, ?, NULL)",
            (user_id, ticket_hash, now + 60),
        )
    return ticket


def consume_ws_ticket(database: Database, ticket: str) -> int | None:
    ticket_hash = hashlib.sha256(ticket.encode("ascii", errors="ignore")).hexdigest()
    now = datetime.now(timezone.utc).timestamp()
    with database.connect() as connection:
        updated = connection.execute(
            "UPDATE ws_tickets SET used_at = ? WHERE ticket_hash = ? AND expires_at > ? AND used_at IS NULL",
            (now, ticket_hash, now),
        )
        if updated.rowcount != 1:
            return None
        row = connection.execute("SELECT user_id FROM ws_tickets WHERE ticket_hash = ?", (ticket_hash,)).fetchone()
        return int(row["user_id"]) if row else None

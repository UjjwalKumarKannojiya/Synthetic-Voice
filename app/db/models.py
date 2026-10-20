"""SQLAlchemy schema shared by local SQLite and hosted PostgreSQL."""

from __future__ import annotations

import sqlalchemy as sa


metadata = sa.MetaData()

users = sa.Table(
    "users",
    metadata,
    sa.Column("id", sa.Integer, primary_key=True),
    sa.Column("username", sa.String(40), nullable=True, unique=True),
    sa.Column("email", sa.String(320), nullable=True),
    sa.Column("display_name", sa.String(120), nullable=True),
    sa.Column("password_salt", sa.String(64), nullable=True),
    sa.Column("password_hash", sa.String(512), nullable=False),
    sa.Column("is_active", sa.Boolean, nullable=False, server_default=sa.true()),
    sa.Column("email_verified", sa.Boolean, nullable=False, server_default=sa.false()),
    sa.Column("created_at", sa.String(40), nullable=False),
    sa.Column("last_login_at", sa.String(40), nullable=True),
)
sa.Index("uq_users_email", users.c.email, unique=True)

auth_sessions = sa.Table(
    "auth_sessions",
    metadata,
    sa.Column("token_hash", sa.String(128), primary_key=True),
    sa.Column("user_id", sa.Integer, sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
    sa.Column("created_at", sa.String(40), nullable=True),
    sa.Column("expires_at", sa.Float, nullable=False),
    sa.Column("revoked_at", sa.Float, nullable=True),
    sa.Column("user_agent", sa.String(512), nullable=True),
)

login_attempts = sa.Table(
    "login_attempts",
    metadata,
    sa.Column("id", sa.Integer, primary_key=True),
    sa.Column("email_lower", sa.String(320), nullable=False),
    sa.Column("ip", sa.String(64), nullable=False),
    sa.Column("action", sa.String(24), nullable=False, server_default="login"),
    sa.Column("success", sa.Boolean, nullable=False),
    sa.Column("created_at", sa.Float, nullable=False),
)
sa.Index("ix_login_attempts_key_time", login_attempts.c.email_lower, login_attempts.c.ip, login_attempts.c.created_at)

ws_tickets = sa.Table(
    "ws_tickets",
    metadata,
    sa.Column("id", sa.Integer, primary_key=True),
    sa.Column("user_id", sa.Integer, sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
    sa.Column("ticket_hash", sa.String(128), nullable=False, unique=True),
    sa.Column("expires_at", sa.Float, nullable=False),
    sa.Column("used_at", sa.Float, nullable=True),
)

analyses = sa.Table(
    "analyses",
    metadata,
    sa.Column("id", sa.Integer, primary_key=True),
    sa.Column("user_id", sa.Integer, sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=True),
    sa.Column("created_at", sa.String(40), nullable=False),
    sa.Column("source", sa.String(80), nullable=False),
    sa.Column("name", sa.String(512), nullable=False),
    sa.Column("duration_s", sa.Float, nullable=False),
    sa.Column("sample_rate", sa.Integer, nullable=False),
    sa.Column("mean_prob", sa.Float, nullable=True),
    sa.Column("max_prob", sa.Float, nullable=True),
    sa.Column("verdict", sa.String(80), nullable=False),
    sa.Column("speech_ratio", sa.Float, nullable=False),
    sa.Column("latency_ms", sa.Float, nullable=False),
    sa.Column("model_version", sa.String(120), nullable=False),
    sa.Column("threshold", sa.Float, nullable=False),
    sa.Column("band", sa.Float, nullable=False),
)
sa.Index("ix_analyses_user_created", analyses.c.user_id, analyses.c.created_at)

windows = sa.Table(
    "windows",
    metadata,
    sa.Column("id", sa.Integer, primary_key=True),
    sa.Column("analysis_id", sa.Integer, sa.ForeignKey("analyses.id", ondelete="CASCADE"), nullable=False),
    sa.Column("t_start", sa.Float, nullable=False),
    sa.Column("t_end", sa.Float, nullable=False),
    sa.Column("prob", sa.Float, nullable=True),
    sa.Column("speech", sa.Boolean, nullable=False),
)

settings = sa.Table(
    "settings",
    metadata,
    sa.Column("id", sa.Integer, primary_key=True),
    sa.Column("user_id", sa.Integer, sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=True),
    sa.Column("key", sa.String(120), nullable=False),
    sa.Column("value", sa.Text, nullable=False),
    sa.UniqueConstraint("user_id", "key", name="uq_settings_user_key"),
)
sa.Index(
    "uq_settings_legacy_key",
    settings.c.key,
    unique=True,
    sqlite_where=settings.c.user_id.is_(None),
    postgresql_where=settings.c.user_id.is_(None),
)


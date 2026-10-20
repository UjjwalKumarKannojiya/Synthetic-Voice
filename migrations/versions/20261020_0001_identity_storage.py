"""Add account security, tickets and owner-ready data columns.

Existing analysis rows and settings are retained with ``user_id`` NULL. They are legacy records and
must not be exposed to a newly registered account by a later authorization phase.
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

from app.db.models import metadata


revision = "20261020_0001"
down_revision = None
branch_labels = None
depends_on = None


def _columns(table: str) -> set[str]:
    return {column["name"] for column in sa.inspect(op.get_bind()).get_columns(table)}


def _tables() -> set[str]:
    return set(sa.inspect(op.get_bind()).get_table_names())


def upgrade() -> None:
    existing = _tables()
    if not existing:
        metadata.create_all(op.get_bind())
        return

    if "users" in existing:
        current = _columns("users")
        for name, column in (
            ("email", sa.Column("email", sa.String(320), nullable=True)),
            ("display_name", sa.Column("display_name", sa.String(120), nullable=True)),
            ("is_active", sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true())),
            ("email_verified", sa.Column("email_verified", sa.Boolean(), nullable=False, server_default=sa.false())),
            ("last_login_at", sa.Column("last_login_at", sa.String(40), nullable=True)),
        ):
            if name not in current:
                op.add_column("users", column)

    if "analyses" in existing and "user_id" not in _columns("analyses"):
        bind = op.get_bind()
        preserve_windows = bind.dialect.name == "sqlite" and "windows" in existing
        if preserve_windows:
            bind.exec_driver_sql(
                "CREATE TEMP TABLE _v1_windows_preserve AS "
                "SELECT id, analysis_id, t_start, t_end, prob, speech FROM windows"
            )
        with op.batch_alter_table("analyses", recreate="always" if bind.dialect.name == "sqlite" else "auto") as batch:
            batch.add_column(sa.Column("user_id", sa.Integer(), nullable=True))
            batch.create_foreign_key("fk_analyses_user_id_users", "users", ["user_id"], ["id"], ondelete="CASCADE")
        if preserve_windows:
            bind.exec_driver_sql(
                "INSERT OR IGNORE INTO windows(id, analysis_id, t_start, t_end, prob, speech) "
                "SELECT id, analysis_id, t_start, t_end, prob, speech FROM _v1_windows_preserve"
            )
            bind.exec_driver_sql("DROP TABLE _v1_windows_preserve")

    if "auth_sessions" in existing:
        current = _columns("auth_sessions")
        for name, column in (
            ("created_at", sa.Column("created_at", sa.String(40), nullable=True)),
            ("revoked_at", sa.Column("revoked_at", sa.Float(), nullable=True)),
            ("user_agent", sa.Column("user_agent", sa.String(512), nullable=True)),
        ):
            if name not in current:
                op.add_column("auth_sessions", column)

    if "settings" in existing and "id" not in _columns("settings"):
        op.rename_table("settings", "settings_legacy")
        op.create_table(
            "settings",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=True),
            sa.Column("key", sa.String(120), nullable=False),
            sa.Column("value", sa.Text(), nullable=False),
            sa.UniqueConstraint("user_id", "key", name="uq_settings_user_key"),
        )
        op.get_bind().execute(sa.text(
            "INSERT INTO settings(user_id, key, value) SELECT NULL, key, value FROM settings_legacy"
        ))
        op.drop_table("settings_legacy")

    metadata.create_all(op.get_bind())
    indexes = {item["name"] for item in sa.inspect(op.get_bind()).get_indexes("settings")}
    if "uq_settings_legacy_key" not in indexes:
        op.create_index(
            "uq_settings_legacy_key",
            "settings",
            ["key"],
            unique=True,
            sqlite_where=sa.text("user_id IS NULL"),
            postgresql_where=sa.text("user_id IS NULL"),
        )


def downgrade() -> None:
    raise RuntimeError(
        "This migration is intentionally forward-only: V1 data may include per-user settings. "
        "Restore the verified pre-V1 SQLite backup to roll back safely."
    )

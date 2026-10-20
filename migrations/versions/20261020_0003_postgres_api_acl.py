"""Keep VoiceGuard tables private from the Supabase Data API roles.

The application authenticates users in FastAPI and connects to PostgreSQL with its
server-side database role. It does not use Supabase Auth or the Supabase Data API.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op


revision = "20261020_0003"
down_revision = "20261020_0002"
branch_labels = None
depends_on = None

_APP_TABLES = (
    "users",
    "auth_sessions",
    "login_attempts",
    "ws_tickets",
    "analyses",
    "windows",
    "settings",
    "alembic_version",
)
_APP_SEQUENCE_TABLES = (
    "users",
    "login_attempts",
    "ws_tickets",
    "analyses",
    "windows",
    "settings",
)
_SUPABASE_API_ROLES = ("anon", "authenticated", "service_role")


def upgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name != "postgresql":
        return

    existing = set(sa.inspect(bind).get_table_names(schema="public"))
    role_parameters = {
        f"role_{index}": role for index, role in enumerate(_SUPABASE_API_ROLES)
    }
    role_placeholders = ", ".join(f":{name}" for name in role_parameters)
    role_rows = bind.execute(
        sa.text(f"SELECT rolname FROM pg_roles WHERE rolname IN ({role_placeholders})"),
        role_parameters,
    ).fetchall()
    api_roles = sorted({row[0] for row in role_rows})
    if not api_roles:
        return

    preparer = bind.dialect.identifier_preparer
    roles_sql = ", ".join(preparer.quote(role) for role in api_roles)

    for table in _APP_TABLES:
        if table not in existing:
            continue
        table_sql = f"{preparer.quote_schema('public')}.{preparer.quote(table)}"
        op.execute(sa.text(f"ALTER TABLE {table_sql} ENABLE ROW LEVEL SECURITY"))
        op.execute(sa.text(f"REVOKE ALL PRIVILEGES ON TABLE {table_sql} FROM {roles_sql}"))

    for table in _APP_SEQUENCE_TABLES:
        if table not in existing:
            continue
        sequence = bind.execute(
            sa.text("SELECT pg_get_serial_sequence(:table_name, 'id')"),
            {"table_name": f"public.{table}"},
        ).scalar()
        if not sequence:
            continue
        schema_name, sequence_name = sequence.rsplit(".", 1)
        sequence_sql = (
            f"{preparer.quote_schema(schema_name)}.{preparer.quote(sequence_name)}"
        )
        op.execute(
            sa.text(f"REVOKE ALL PRIVILEGES ON SEQUENCE {sequence_sql} FROM {roles_sql}")
        )

    op.execute(
        sa.text(
            "ALTER DEFAULT PRIVILEGES IN SCHEMA public "
            f"REVOKE ALL PRIVILEGES ON TABLES FROM {roles_sql}"
        )
    )
    op.execute(
        sa.text(
            "ALTER DEFAULT PRIVILEGES IN SCHEMA public "
            f"REVOKE ALL PRIVILEGES ON SEQUENCES FROM {roles_sql}"
        )
    )


def downgrade() -> None:
    raise RuntimeError(
        "This security migration is forward-only; do not restore broad public API grants."
    )

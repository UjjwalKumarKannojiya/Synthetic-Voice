from __future__ import annotations

import importlib
from types import SimpleNamespace

from sqlalchemy.dialects import postgresql


MIGRATION = importlib.import_module(
    "migrations.versions.20261020_0003_postgres_api_acl"
)


class _Result:
    def __init__(self, rows=(), scalar=None):
        self._rows = rows
        self._scalar = scalar

    def fetchall(self):
        return self._rows

    def scalar(self):
        return self._scalar


class _PostgresBind:
    def __init__(self):
        self.dialect = postgresql.dialect()

    def execute(self, statement, parameters=None):
        sql = str(statement)
        if "FROM pg_roles" in sql:
            assert parameters == {
                "role_0": "anon",
                "role_1": "authenticated",
                "role_2": "service_role",
            }
            return _Result([(role,) for role in ("anon", "authenticated", "service_role")])
        if "pg_get_serial_sequence" in sql:
            table = parameters["table_name"].rsplit(".", 1)[1]
            if table == "auth_sessions":
                return _Result(scalar=None)
            return _Result(scalar=f"public.{table}_id_seq")
        raise AssertionError(f"Unexpected SQL in migration test: {sql}")


def test_postgres_migration_enables_rls_and_revokes_data_api_grants(monkeypatch):
    bind = _PostgresBind()
    existing_tables = {
        "users",
        "auth_sessions",
        "login_attempts",
        "ws_tickets",
        "analyses",
        "windows",
        "settings",
        "alembic_version",
    }
    monkeypatch.setattr(
        MIGRATION.sa,
        "inspect",
        lambda current_bind: SimpleNamespace(
            get_table_names=lambda schema: sorted(existing_tables)
        ),
    )
    statements = []
    monkeypatch.setattr(
        MIGRATION,
        "op",
        SimpleNamespace(get_bind=lambda: bind, execute=lambda statement: statements.append(str(statement))),
    )

    MIGRATION.upgrade()

    assert sum("ENABLE ROW LEVEL SECURITY" in sql for sql in statements) == len(existing_tables)
    assert sum(
        "REVOKE ALL PRIVILEGES ON TABLE public." in sql for sql in statements
    ) == len(existing_tables)
    assert sum(
        "REVOKE ALL PRIVILEGES ON SEQUENCE public." in sql for sql in statements
    ) == 6
    assert any("ALTER DEFAULT PRIVILEGES" in sql and "ON TABLES" in sql for sql in statements)
    assert any("ALTER DEFAULT PRIVILEGES" in sql and "ON SEQUENCES" in sql for sql in statements)
    assert all(
        all(role in sql for role in ("anon", "authenticated", "service_role"))
        for sql in statements
        if "REVOKE" in sql
    )


def test_non_postgres_database_skips_supabase_security_ddl(monkeypatch):
    statements = []
    monkeypatch.setattr(
        MIGRATION,
        "op",
        SimpleNamespace(
            get_bind=lambda: SimpleNamespace(dialect=SimpleNamespace(name="sqlite")),
            execute=lambda statement: statements.append(str(statement)),
        ),
    )

    MIGRATION.upgrade()

    assert statements == []

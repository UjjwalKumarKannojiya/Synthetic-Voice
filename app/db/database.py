"""SQLAlchemy connection and Alembic migration wrapper."""

from __future__ import annotations

import os
import re
from collections.abc import Iterator, Mapping, Sequence
from contextlib import contextmanager
from pathlib import Path
from typing import Any

import sqlalchemy as sa
from alembic import command
from alembic.config import Config
from sqlalchemy.engine import Connection, Engine, Result
from sqlalchemy.engine.url import URL, make_url
from sqlalchemy.pool import NullPool


class CompatRow(Mapping[str, Any]):
    """Mapping row that also preserves sqlite3.Row's integer indexing."""

    def __init__(self, row: Any):
        self._mapping = row._mapping
        self._values = tuple(row)

    def __getitem__(self, key: str | int) -> Any:
        if isinstance(key, int):
            return self._values[key]
        return self._mapping[key]

    def __iter__(self):
        return iter(self._mapping)

    def __len__(self) -> int:
        return len(self._mapping)


class CompatResult:
    def __init__(self, result: Result[Any]):
        self._result = result
        self.lastrowid = result.lastrowid
        self.rowcount = result.rowcount

    def fetchone(self) -> CompatRow | None:
        row = self._result.fetchone()
        return CompatRow(row) if row is not None else None

    def fetchall(self) -> list[CompatRow]:
        return [CompatRow(row) for row in self._result.fetchall()]

    def __iter__(self):
        for row in self._result:
            yield CompatRow(row)


def _named_statement(sql: str, values: Sequence[Any]) -> tuple[sa.TextClause, dict[str, Any]]:
    index = 0

    def parameter(_: re.Match[str]) -> str:
        nonlocal index
        name = f"p{index}"
        index += 1
        return f":{name}"

    statement = re.sub(r"\?", parameter, sql)
    if index != len(values):
        raise ValueError(f"SQL parameter count mismatch: expected {index}, received {len(values)}")
    return sa.text(statement), {f"p{i}": value for i, value in enumerate(values)}


class ConnectionAdapter:
    """Keep existing CRUD call sites stable while executing through SQLAlchemy."""

    def __init__(self, connection: Connection):
        self._connection = connection

    def execute(self, sql: str, values: Sequence[Any] = ()) -> CompatResult:
        statement, parameters = _named_statement(sql, values)
        return CompatResult(self._connection.execute(statement, parameters))

    def executemany(self, sql: str, rows: Sequence[Sequence[Any]]) -> CompatResult:
        rows = list(rows)
        if not rows:
            return CompatResult(self._connection.execute(sa.text("SELECT 1 WHERE 1=0")))
        statement, _ = _named_statement(sql, rows[0])
        params = [{f"p{i}": value for i, value in enumerate(row)} for row in rows]
        return CompatResult(self._connection.execute(statement, params))

    def __enter__(self) -> ConnectionAdapter:
        return self

    def __exit__(self, exc_type: Any, exc: Any, traceback: Any) -> None:
        try:
            if exc_type is None:
                self._connection.commit()
            else:
                self._connection.rollback()
        finally:
            self._connection.close()


class Database:
    def __init__(self, path_or_url: str | Path):
        raw = str(path_or_url)
        if "://" in raw:
            # psycopg 3 is the declared PostgreSQL driver. Provider URLs commonly
            # use the driver-neutral postgresql:// or postgres:// scheme.
            if raw.startswith("postgresql://"):
                raw = "postgresql+psycopg://" + raw.removeprefix("postgresql://")
            elif raw.startswith("postgres://"):
                raw = "postgresql+psycopg://" + raw.removeprefix("postgres://")
            url = make_url(raw)
            if url.get_backend_name() == "sqlite" and url.database not in {None, ":memory:"}:
                Path(url.database).expanduser().resolve().parent.mkdir(parents=True, exist_ok=True)
            connect_args = {"check_same_thread": False, "timeout": 30} if url.get_backend_name() == "sqlite" else {}
        else:
            path = Path(path_or_url).expanduser().resolve()
            path.parent.mkdir(parents=True, exist_ok=True)
            url = URL.create("sqlite", database=str(path))
            connect_args = {"check_same_thread": False, "timeout": 30}
        self.url = url
        if os.environ.get("VERCEL") == "1" and url.get_backend_name() != "postgresql":
            raise RuntimeError("Vercel deployments require persistent PostgreSQL; SQLite files are not durable")
        pool_options = {}
        if os.environ.get("VERCEL") == "1" and url.get_backend_name() == "postgresql":
            if url.port == 6543:
                # Supabase transaction poolers expect one-off client connections and
                # do not support Psycopg's automatic prepared statements.
                pool_options = {"poolclass": NullPool}
                connect_args["prepare_threshold"] = None
            else:
                pool_options = {"pool_size": 1, "max_overflow": 0, "pool_recycle": 300}
        self.engine: Engine = sa.create_engine(url, connect_args=connect_args, pool_pre_ping=True, **pool_options)
        if url.get_backend_name() == "sqlite":
            @sa.event.listens_for(self.engine, "connect")
            def _enable_foreign_keys(connection: Any, _: Any) -> None:
                cursor = connection.cursor()
                cursor.execute("PRAGMA foreign_keys=ON")
                cursor.close()

    def connect(self) -> ConnectionAdapter:
        return ConnectionAdapter(self.engine.connect())

    def initialize(self) -> None:
        project_root = Path(__file__).resolve().parents[2]
        config = Config(str(project_root / "alembic.ini"))
        config.set_main_option("script_location", str(project_root / "migrations"))
        connection = self.engine.connect()
        postgres_lock = self.url.get_backend_name() == "postgresql"
        config.attributes["connection"] = connection
        try:
            if postgres_lock:
                # Serverless instances can cold-start together. Keep a transaction-scoped
                # advisory lock and the Alembic upgrade on the same connection.
                with connection.begin():
                    connection.execute(sa.text("SELECT pg_advisory_xact_lock(741935120)"))
                    command.upgrade(config, "head")
            else:
                command.upgrade(config, "head")
        finally:
            connection.close()

    @contextmanager
    def transaction(self) -> Iterator[ConnectionAdapter]:
        connection = self.connect()
        try:
            yield connection
            connection._connection.commit()
        except Exception:
            connection._connection.rollback()
            raise
        finally:
            connection._connection.close()

    def dispose(self) -> None:
        self.engine.dispose()


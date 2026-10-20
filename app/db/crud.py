"""Persistence operations for analysis results."""

from __future__ import annotations

import csv
import io
import json
from datetime import datetime, timezone
from typing import Any

from .database import Database


def save_analysis(database: Database, source: str, name: str, result: dict[str, Any], latency_ms: float, model_version: str, user_id: int | None = None) -> int:
    created_at = datetime.now(timezone.utc).isoformat()
    with database.connect() as connection:
        cursor = connection.execute(
            """
            INSERT INTO analyses
            (user_id, created_at, source, name, duration_s, sample_rate, mean_prob, max_prob,
             verdict, speech_ratio, latency_ms, model_version, threshold, band)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            RETURNING id
            """,
            (
                user_id,
                created_at,
                source,
                name,
                result["duration_s"],
                result["sample_rate"],
                result["mean_prob"],
                result["max_prob"],
                result["verdict"],
                result["speech_ratio"],
                latency_ms,
                model_version,
                result["threshold"],
                result["uncertain_band"],
            ),
        )
        analysis_id = int(cursor.lastrowid)
        connection.executemany(
            "INSERT INTO windows (analysis_id, t_start, t_end, prob, speech) VALUES (?, ?, ?, ?, ?)",
            [
                (analysis_id, window["t_start"], window["t_end"], window["prob"], bool(window["speech"]))
                for window in result["windows"]
            ],
        )
        return analysis_id


def _analysis_payload(row: Any, windows: list[Any] | None = None) -> dict[str, Any]:
    payload = dict(row)
    payload["windows"] = [dict(window) for window in (windows or [])]
    return payload


def get_analysis(database: Database, analysis_id: int, user_id: int | None = None) -> dict[str, Any] | None:
    with database.connect() as connection:
        if user_id is None:
            row = connection.execute("SELECT * FROM analyses WHERE id = ?", (analysis_id,)).fetchone()
        else:
            row = connection.execute("SELECT * FROM analyses WHERE id = ? AND user_id = ?", (analysis_id, user_id)).fetchone()
        if row is None:
            return None
        windows = connection.execute(
            "SELECT t_start, t_end, prob, speech FROM windows WHERE analysis_id = ? ORDER BY t_start",
            (analysis_id,),
        ).fetchall()
        return _analysis_payload(row, windows)


def list_analyses(database: Database, source: str | None = None, verdict: str | None = None, user_id: int | None = None) -> list[dict[str, Any]]:
    clauses: list[str] = []
    values: list[str] = []
    if user_id is not None:
        clauses.append("user_id = ?")
        values.append(user_id)
    if source:
        clauses.append("source = ?")
        values.append(source)
    if verdict:
        clauses.append("verdict = ?")
        values.append(verdict)
    query = "SELECT * FROM analyses"
    if clauses:
        query += " WHERE " + " AND ".join(clauses)
    query += " ORDER BY created_at DESC"
    with database.connect() as connection:
        return [_analysis_payload(row) for row in connection.execute(query, values).fetchall()]


def dashboard_summary(database: Database, user_id: int | None = None) -> dict[str, Any]:
    rows = list_analyses(database, user_id=user_id)
    flagged = sum(row["verdict"] == "Likely Synthetic" for row in rows)
    uncertain = sum(row["verdict"] == "Uncertain" for row in rows)
    latencies = [row["latency_ms"] for row in rows]
    return {
        "total": len(rows),
        "flagged": flagged,
        "uncertain": uncertain,
        "flagged_pct": flagged / len(rows) if rows else 0.0,
        "avg_latency_ms": sum(latencies) / len(latencies) if latencies else None,
        "recent": rows[:10],
        "series": [{"created_at": row["created_at"], "mean_prob": row["mean_prob"]} for row in rows[:20]],
    }


def export_csv(database: Database, user_id: int | None = None) -> str:
    rows = list_analyses(database, user_id=user_id)
    output = io.StringIO()
    fields = ["id", "created_at", "source", "name", "duration_s", "mean_prob", "max_prob", "verdict", "latency_ms"]
    writer = csv.DictWriter(output, fieldnames=fields)
    writer.writeheader()
    writer.writerows({field: row[field] for field in fields} for row in rows)
    return output.getvalue()


def clear_analyses(database: Database, user_id: int | None = None) -> None:
    with database.connect() as connection:
        if user_id is None:
            connection.execute("DELETE FROM analyses")
        else:
            connection.execute("DELETE FROM analyses WHERE user_id = ?", (user_id,))


def read_settings(database: Database, user_id: int | None = None) -> dict[str, Any]:
    with database.connect() as connection:
        if user_id is None:
            values = connection.execute("SELECT key, value FROM settings WHERE user_id IS NULL").fetchall()
        else:
            values = connection.execute("SELECT key, value FROM settings WHERE user_id = ?", (user_id,)).fetchall()
    return {row["key"]: json.loads(row["value"]) for row in values}


def write_settings(database: Database, values: dict[str, Any], user_id: int | None = None) -> dict[str, Any]:
    with database.connect() as connection:
        if user_id is None:
            connection.executemany(
                "INSERT INTO settings(user_id, key, value) VALUES (NULL, ?, ?) "
                "ON CONFLICT(key) WHERE user_id IS NULL DO UPDATE SET value = excluded.value",
                [(key, json.dumps(value)) for key, value in values.items()],
            )
        else:
            connection.executemany(
                "INSERT INTO settings(user_id, key, value) VALUES (?, ?, ?) "
                "ON CONFLICT(user_id, key) DO UPDATE SET value = excluded.value",
                [(user_id, key, json.dumps(value)) for key, value in values.items()],
            )
    return read_settings(database, user_id)

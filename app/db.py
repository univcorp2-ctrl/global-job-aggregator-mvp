from __future__ import annotations

import json
import sqlite3
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from app.models import NormalizedJob

SCHEMA = """
CREATE TABLE IF NOT EXISTS jobs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    source TEXT NOT NULL,
    external_id TEXT NOT NULL,
    title TEXT NOT NULL,
    company TEXT,
    url TEXT,
    location TEXT,
    compensation TEXT,
    contract_type TEXT,
    remote TEXT,
    japan_ok TEXT,
    required_skills TEXT NOT NULL DEFAULT '[]',
    ai_relevance REAL NOT NULL DEFAULT 0,
    fit_score REAL NOT NULL DEFAULT 0,
    expected_monthly_income TEXT,
    application_priority TEXT NOT NULL DEFAULT 'C',
    proposal_draft TEXT,
    status TEXT NOT NULL DEFAULT 'new',
    description TEXT,
    published_at TEXT,
    fetched_at TEXT NOT NULL,
    raw_json TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(source, external_id)
);

CREATE INDEX IF NOT EXISTS idx_jobs_priority ON jobs(application_priority, ai_relevance);
CREATE INDEX IF NOT EXISTS idx_jobs_source ON jobs(source);
CREATE INDEX IF NOT EXISTS idx_jobs_status ON jobs(status);
CREATE INDEX IF NOT EXISTS idx_jobs_title ON jobs(title);

CREATE TABLE IF NOT EXISTS source_runs (
    source TEXT PRIMARY KEY,
    last_attempt_at TEXT,
    last_success_at TEXT,
    last_status TEXT,
    last_error TEXT,
    last_count INTEGER NOT NULL DEFAULT 0
);
"""

JOB_COLUMNS = [
    "source",
    "external_id",
    "title",
    "company",
    "url",
    "location",
    "compensation",
    "contract_type",
    "remote",
    "japan_ok",
    "required_skills",
    "ai_relevance",
    "fit_score",
    "expected_monthly_income",
    "application_priority",
    "proposal_draft",
    "status",
    "description",
    "published_at",
    "fetched_at",
    "raw_json",
    "updated_at",
]


def utc_now() -> str:
    return datetime.now(UTC).isoformat()


def connect(db_path: str | Path) -> sqlite3.Connection:
    path = Path(db_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    return conn


def init_db(db_path: str | Path) -> None:
    with connect(db_path) as conn:
        conn.executescript(SCHEMA)
        conn.commit()


def upsert_job(conn: sqlite3.Connection, job: NormalizedJob) -> bool:
    before = conn.total_changes
    record = job.to_record()
    placeholders = ", ".join(f":{col}" for col in JOB_COLUMNS)
    columns = ", ".join(JOB_COLUMNS)
    updates = ", ".join(
        f"{col}=excluded.{col}"
        for col in JOB_COLUMNS
        if col not in {"source", "external_id", "status"}
    )
    sql = f"""
    INSERT INTO jobs ({columns})
    VALUES ({placeholders})
    ON CONFLICT(source, external_id) DO UPDATE SET
        {updates},
        status=jobs.status
    """
    conn.execute(sql, record)
    conn.commit()
    return conn.total_changes > before


def _row_to_dict(row: sqlite3.Row) -> dict[str, Any]:
    item = dict(row)
    try:
        item["required_skills"] = json.loads(item.get("required_skills") or "[]")
    except json.JSONDecodeError:
        item["required_skills"] = []
    try:
        item["raw"] = json.loads(item.get("raw_json") or "{}")
    except json.JSONDecodeError:
        item["raw"] = {}
    return item


def list_jobs(
    conn: sqlite3.Connection,
    *,
    q: str | None = None,
    source: str | None = None,
    status: str | None = None,
    priority: str | None = None,
    limit: int = 100,
) -> list[dict[str, Any]]:
    conditions: list[str] = []
    params: dict[str, Any] = {"limit": max(1, min(limit, 500))}
    if q:
        params["q"] = f"%{q.lower()}%"
        conditions.append(
            "(lower(title) LIKE :q OR lower(company) LIKE :q OR lower(description) LIKE :q "
            "OR lower(required_skills) LIKE :q)"
        )
    if source:
        conditions.append("source = :source")
        params["source"] = source
    if status:
        conditions.append("status = :status")
        params["status"] = status
    if priority:
        conditions.append("application_priority = :priority")
        params["priority"] = priority
    where = f"WHERE {' AND '.join(conditions)}" if conditions else ""
    sql = f"""
    SELECT * FROM jobs
    {where}
    ORDER BY
      CASE application_priority WHEN 'A' THEN 1 WHEN 'B' THEN 2 WHEN 'C' THEN 3 ELSE 4 END,
      ai_relevance DESC,
      COALESCE(published_at, fetched_at) DESC
    LIMIT :limit
    """
    return [_row_to_dict(row) for row in conn.execute(sql, params).fetchall()]


def get_job(conn: sqlite3.Connection, job_id: int) -> dict[str, Any] | None:
    row = conn.execute("SELECT * FROM jobs WHERE id = ?", (job_id,)).fetchone()
    return _row_to_dict(row) if row else None


def source_counts(conn: sqlite3.Connection) -> list[dict[str, Any]]:
    rows = conn.execute(
        "SELECT source, COUNT(*) AS count FROM jobs GROUP BY source ORDER BY count DESC"
    ).fetchall()
    return [dict(row) for row in rows]


def record_source_run(
    conn: sqlite3.Connection,
    source: str,
    *,
    status: str,
    count: int,
    error: str | None = None,
) -> None:
    now = utc_now()
    success = now if status == "success" else None
    conn.execute(
        """
        INSERT INTO source_runs(source, last_attempt_at, last_success_at, last_status, last_error, last_count)
        VALUES(:source, :attempt, :success, :status, :error, :count)
        ON CONFLICT(source) DO UPDATE SET
            last_attempt_at=excluded.last_attempt_at,
            last_success_at=COALESCE(excluded.last_success_at, source_runs.last_success_at),
            last_status=excluded.last_status,
            last_error=excluded.last_error,
            last_count=excluded.last_count
        """,
        {
            "source": source,
            "attempt": now,
            "success": success,
            "status": status,
            "error": error,
            "count": count,
        },
    )
    conn.commit()


def source_due(conn: sqlite3.Connection, source: str, cooldown_hours: float) -> bool:
    row = conn.execute(
        "SELECT last_success_at FROM source_runs WHERE source = ?", (source,)
    ).fetchone()
    if not row or not row["last_success_at"]:
        return True
    try:
        last_success = datetime.fromisoformat(row["last_success_at"])
    except ValueError:
        return True
    return datetime.now(UTC) - last_success >= timedelta(hours=cooldown_hours)

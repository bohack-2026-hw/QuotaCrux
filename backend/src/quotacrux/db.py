"""SQLite storage. One connection per thread; WAL so the API can read while a run writes."""

from __future__ import annotations

import json
import sqlite3
import threading
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from . import config

SCHEMA = """
CREATE TABLE IF NOT EXISTS tasks (
    task_id TEXT PRIMARY KEY,
    family TEXT NOT NULL,
    split TEXT NOT NULL,
    manifest_json TEXT NOT NULL,
    manifest_sha256 TEXT NOT NULL,
    registered_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS snapshots (
    snapshot_id TEXT PRIMARY KEY,
    version INTEGER NOT NULL UNIQUE,
    parent_snapshot_id TEXT,
    source_run_id TEXT,
    created_at TEXT NOT NULL,
    diff_json TEXT NOT NULL DEFAULT '{}'
);

CREATE TABLE IF NOT EXISTS settings (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS runs (
    run_id TEXT PRIMARY KEY,
    task_id TEXT NOT NULL REFERENCES tasks(task_id),
    mode TEXT NOT NULL,
    snapshot_id TEXT NOT NULL,
    config_json TEXT NOT NULL,
    config_fingerprint TEXT NOT NULL,
    status TEXT NOT NULL,
    stop_reason TEXT,
    stop_detail TEXT,
    best_candidate_id TEXT,
    final_evaluation_id TEXT,
    stop_requested INTEGER NOT NULL DEFAULT 0,
    started_at TEXT NOT NULL,
    loop_ended_at TEXT,
    ended_at TEXT
);

CREATE TABLE IF NOT EXISTS steps (
    step_id TEXT PRIMARY KEY,
    run_id TEXT NOT NULL REFERENCES runs(run_id),
    seq INTEGER NOT NULL,
    actor TEXT NOT NULL,
    action TEXT NOT NULL,
    status TEXT NOT NULL,
    purpose TEXT,
    expected_result TEXT,
    verification TEXT,
    hypothesis TEXT,
    params_json TEXT NOT NULL DEFAULT '{}',
    result_json TEXT NOT NULL DEFAULT '{}',
    next_decision TEXT,
    model_call_id TEXT,
    tool_call_id TEXT,
    candidate_id TEXT,
    evaluation_id TEXT,
    started_at TEXT NOT NULL,
    ended_at TEXT,
    UNIQUE (run_id, seq)
);

CREATE TABLE IF NOT EXISTS model_calls (
    call_id TEXT PRIMARY KEY,
    run_id TEXT NOT NULL REFERENCES runs(run_id),
    provider TEXT NOT NULL,
    role TEXT NOT NULL,
    model_requested TEXT NOT NULL,
    model_returned TEXT,
    reasoning_effort TEXT,
    max_output_tokens INTEGER,
    status TEXT NOT NULL,
    error_kind TEXT,
    error_message TEXT,
    request_id TEXT,
    input_tokens INTEGER,
    cached_input_tokens INTEGER,
    output_tokens INTEGER,
    reasoning_tokens INTEGER,
    usage_source TEXT NOT NULL,
    estimated_input_tokens INTEGER,
    cost_usd REAL,
    cost_status TEXT NOT NULL,
    price_version TEXT,
    latency_s REAL,
    request_path TEXT,
    response_path TEXT,
    started_at TEXT NOT NULL,
    ended_at TEXT
);

CREATE TABLE IF NOT EXISTS tool_calls (
    call_id TEXT PRIMARY KEY,
    run_id TEXT NOT NULL REFERENCES runs(run_id),
    tool TEXT NOT NULL,
    params_json TEXT NOT NULL DEFAULT '{}',
    status TEXT NOT NULL,
    error_kind TEXT,
    error_message TEXT,
    duration_s REAL,
    output_path TEXT,
    started_at TEXT NOT NULL,
    ended_at TEXT
);

CREATE TABLE IF NOT EXISTS candidates (
    run_id TEXT NOT NULL REFERENCES runs(run_id),
    candidate_id TEXT NOT NULL,
    seq INTEGER NOT NULL,
    parent_candidate_id TEXT,
    origin TEXT NOT NULL,
    model_call_id TEXT,
    code_path TEXT NOT NULL,
    code_sha256 TEXT NOT NULL,
    created_at TEXT NOT NULL,
    PRIMARY KEY (run_id, candidate_id)
);

CREATE TABLE IF NOT EXISTS evaluations (
    evaluation_id TEXT PRIMARY KEY,
    run_id TEXT,
    candidate_id TEXT,
    task_id TEXT NOT NULL,
    dataset TEXT NOT NULL,
    dataset_sha256 TEXT NOT NULL,
    status TEXT NOT NULL,
    executed INTEGER NOT NULL,
    format_ok INTEGER,
    correct INTEGER,
    improved INTEGER,
    goal_met INTEGER,
    speedup REAL,
    candidate_median_s REAL,
    baseline_median_s REAL,
    detail_json TEXT NOT NULL,
    evaluator_version TEXT NOT NULL,
    started_at TEXT NOT NULL,
    ended_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS experiences (
    experience_id TEXT PRIMARY KEY,
    family TEXT NOT NULL,
    task_id TEXT NOT NULL,
    split TEXT NOT NULL,
    outcome TEXT NOT NULL,
    conditions_json TEXT NOT NULL,
    action_json TEXT NOT NULL,
    hypothesis TEXT,
    result_json TEXT NOT NULL,
    resources_json TEXT NOT NULL,
    source_json TEXT NOT NULL,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS snapshot_items (
    snapshot_id TEXT NOT NULL REFERENCES snapshots(snapshot_id),
    experience_id TEXT NOT NULL REFERENCES experiences(experience_id),
    PRIMARY KEY (snapshot_id, experience_id)
);

CREATE TABLE IF NOT EXISTS run_experiences (
    run_id TEXT NOT NULL REFERENCES runs(run_id),
    experience_id TEXT NOT NULL REFERENCES experiences(experience_id),
    rank INTEGER NOT NULL,
    matching_features INTEGER NOT NULL,
    PRIMARY KEY (run_id, experience_id)
);

CREATE TABLE IF NOT EXISTS pointer_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ts TEXT NOT NULL,
    from_snapshot_id TEXT,
    to_snapshot_id TEXT NOT NULL,
    reason TEXT,
    actor TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS comparisons (
    comparison_id TEXT PRIMARY KEY,
    status TEXT NOT NULL,
    label TEXT,
    plan_json TEXT NOT NULL,
    summary_json TEXT,
    stop_requested INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL,
    ended_at TEXT
);
CREATE TABLE IF NOT EXISTS comparison_runs (
    comparison_id TEXT NOT NULL REFERENCES comparisons(comparison_id),
    seq INTEGER NOT NULL,
    task_id TEXT NOT NULL,
    snapshot_id TEXT NOT NULL,
    repeat INTEGER NOT NULL,
    run_id TEXT,
    error TEXT,
    PRIMARY KEY (comparison_id, seq)
);

CREATE TABLE IF NOT EXISTS sessions (
    session_id TEXT PRIMARY KEY,
    learn_task TEXT NOT NULL,
    eval_task TEXT NOT NULL,
    base_snapshot_id TEXT NOT NULL,
    phase TEXT NOT NULL,
    status TEXT NOT NULL,
    learn_run_id TEXT,
    new_snapshot_id TEXT,
    comparison_id TEXT,
    detail TEXT,
    created_at TEXT NOT NULL,
    ended_at TEXT
);

CREATE TABLE IF NOT EXISTS events (
    event_id INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id TEXT NOT NULL,
    ts TEXT NOT NULL,
    type TEXT NOT NULL,
    payload_json TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS events_by_run ON events(run_id, event_id);
"""

_local = threading.local()


def now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds")


def connect(path: Path | None = None) -> sqlite3.Connection:
    path = path or config.DB_PATH
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path, timeout=30, isolation_level=None)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def get() -> sqlite3.Connection:
    conn = getattr(_local, "conn", None)
    if conn is None:
        conn = connect()
        init(conn)
        _local.conn = conn
    return conn


MIGRATIONS = {
    "runs": {"retrieval_json": "TEXT", "published_snapshot_id": "TEXT"},
    "comparison_runs": {"arm": "TEXT", "position": "INTEGER"},
}


def init(conn: sqlite3.Connection) -> None:
    conn.executescript(SCHEMA)
    for table, cols in MIGRATIONS.items():
        have = {r["name"] for r in conn.execute(f"PRAGMA table_info({table})")}
        for col, typ in cols.items():
            if col not in have:
                conn.execute(f"ALTER TABLE {table} ADD COLUMN {col} {typ}")
    # v0 is the empty initial snapshot every run can read.
    conn.execute(
        "INSERT OR IGNORE INTO snapshots (snapshot_id, version, parent_snapshot_id, source_run_id, created_at, diff_json)"
        " VALUES ('v0', 0, NULL, NULL, ?, '{}')",
        (now(),),
    )
    conn.execute("INSERT OR IGNORE INTO settings (key, value) VALUES ('active_snapshot_id', 'v0')")


def dumps(obj: Any) -> str:
    return json.dumps(obj, ensure_ascii=False, sort_keys=True, default=str)


def insert(table: str, row: dict[str, Any]) -> None:
    cols = ", ".join(row)
    marks = ", ".join("?" for _ in row)
    get().execute(f"INSERT INTO {table} ({cols}) VALUES ({marks})", tuple(row.values()))


def update(table: str, key_col: str, key: str, fields: dict[str, Any]) -> None:
    sets = ", ".join(f"{k} = ?" for k in fields)
    get().execute(f"UPDATE {table} SET {sets} WHERE {key_col} = ?", (*fields.values(), key))


def one(sql: str, params: tuple = ()) -> sqlite3.Row | None:
    return get().execute(sql, params).fetchone()


def all_rows(sql: str, params: tuple = ()) -> list[sqlite3.Row]:
    return get().execute(sql, params).fetchall()


def add_event(run_id: str, type_: str, payload: dict[str, Any]) -> None:
    timestamp = now()
    insert("events", {"run_id": run_id, "ts": timestamp, "type": type_, "payload_json": dumps(payload)})
    observer = getattr(_local, "event_observer", None)
    if observer is not None:
        observer({"run_id": run_id, "ts": timestamp, "type": type_, "payload": payload})


@contextmanager
def observe_events(observer):
    """Stream committed events to an in-process adapter, confined to this thread."""
    previous = getattr(_local, "event_observer", None)
    _local.event_observer = observer
    try:
        yield
    finally:
        _local.event_observer = previous

from __future__ import annotations

import sqlite3
from pathlib import Path

from typing import Optional, Iterable

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DB_PATH = PROJECT_ROOT / "data" / "app.db"
DEFAULT_SCHEMA_PATH = PROJECT_ROOT / "data" / "schema.sql"


def connect(db_path: Path = DEFAULT_DB_PATH) -> sqlite3.Connection:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON;")
    return conn


def init_db(
    db_path: Path = DEFAULT_DB_PATH,
    schema_path: Path = DEFAULT_SCHEMA_PATH,
) -> None:
    if not schema_path.exists():
        raise FileNotFoundError(f"schema.sql not found: {schema_path}")

    conn = connect(db_path)
    try:
        sql = schema_path.read_text(encoding="utf-8")
        conn.executescript(sql)
        conn.commit()
    finally:
        conn.close()


def insert_a_task(
    title: str,
    deadline_date: str,   # "YYYY-MM-DD"
    total_minutes: int,
    db_path: Path = DEFAULT_DB_PATH,
) -> int:
    if total_minutes < 0:
        raise ValueError("total_minutes must be >= 0")

    conn = connect(db_path)
    try:
        cur = conn.execute(
            """
            INSERT INTO a_tasks (title, deadline_date, total_minutes, remaining_minutes)
            VALUES (?, ?, ?, ?)
            """,
            (title, deadline_date, total_minutes, total_minutes),
        )
        conn.commit()
        return int(cur.lastrowid)
    finally:
        conn.close()


def list_a_tasks(db_path: Path = DEFAULT_DB_PATH) -> list[dict]:
    conn = connect(db_path)
    try:
        rows = conn.execute(
            """
            SELECT id, title, deadline_date, total_minutes, remaining_minutes, created_at
            FROM a_tasks
            ORDER BY deadline_date ASC, id ASC
            """
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def upsert_daily_log(
    log_date: str,      # "YYYY-MM-DD"
    a_task_id: int,
    actual_minutes: int,
    reflection: str = "",
    db_path: Path = DEFAULT_DB_PATH,
) -> None:
    if actual_minutes < 0:
        raise ValueError("actual_minutes must be >= 0")

    conn = connect(db_path)
    try:
        conn.execute(
            """
            INSERT INTO daily_logs (log_date, a_task_id, actual_minutes, reflection)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(log_date, a_task_id) DO UPDATE SET
              actual_minutes = excluded.actual_minutes,
              reflection = excluded.reflection
            """,
            (log_date, a_task_id, actual_minutes, reflection),
        )
        conn.commit()
    finally:
        conn.close()


def recompute_remaining_minutes(
    a_task_id: int,
    db_path: Path = DEFAULT_DB_PATH,
) -> int:
    """
    daily_logs の合計から remaining_minutes を更新して返す
    remaining = max(total - sum(actual), 0)
    """
    conn = connect(db_path)
    try:
        row = conn.execute(
            "SELECT total_minutes FROM a_tasks WHERE id = ?",
            (a_task_id,),
        ).fetchone()
        if row is None:
            raise ValueError(f"a_task_id not found: {a_task_id}")

        total = int(row["total_minutes"])

        sum_row = conn.execute(
            "SELECT COALESCE(SUM(actual_minutes), 0) AS s FROM daily_logs WHERE a_task_id = ?",
            (a_task_id,),
        ).fetchone()
        done = int(sum_row["s"])
        remaining = max(total - done, 0)

        conn.execute(
            "UPDATE a_tasks SET remaining_minutes = ? WHERE id = ?",
            (remaining, a_task_id),
        )
        conn.commit()
        return remaining
    finally:
        conn.close()


def get_daily_logs(
    a_task_id: int,
    db_path: Path = DEFAULT_DB_PATH,
) -> list[dict]:
    conn = connect(db_path)
    try:
        rows = conn.execute(
            """
            SELECT log_date, a_task_id, actual_minutes, reflection, created_at
            FROM daily_logs
            WHERE a_task_id = ?
            ORDER BY log_date ASC
            """,
            (a_task_id,),
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()

#追加
def insert_event(
    event_type: str,      # "B" or "C"
    title: str,
    start_dt: str,        # "YYYY-MM-DDTHH:MM:SS"
    end_dt: str,          # "YYYY-MM-DDTHH:MM:SS"
    remind_start: int = 0,
    remind_end: int = 0,
    note: str = "",
    db_path: Path = DEFAULT_DB_PATH,
) -> int:
    if event_type not in ("B", "C"):
        raise ValueError("event_type must be 'B' or 'C'")

    if start_dt >= end_dt:
        raise ValueError("start_dt must be before end_dt")

    conn = connect(db_path)
    try:
        cur = conn.execute(
            """
            INSERT INTO events (
              type, title, start_dt, end_dt, remind_start, remind_end, note
            )
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (event_type, title, start_dt, end_dt, remind_start, remind_end, note),
        )
        conn.commit()
        return int(cur.lastrowid)
    finally:
        conn.close()


def list_events_by_date(
    target_date: str,     # "YYYY-MM-DD"
    db_path: Path = DEFAULT_DB_PATH,
) -> list[dict]:
    """
    指定日のB/C予定を取得する。
    MVPでは「その日内に開始する予定」を対象にする。
    """
    start = f"{target_date}T00:00:00"
    end = f"{target_date}T23:59:59"

    conn = connect(db_path)
    try:
        rows = conn.execute(
            """
            SELECT id, type, title, start_dt, end_dt, remind_start, remind_end, note
            FROM events
            WHERE start_dt BETWEEN ? AND ?
            ORDER BY start_dt ASC, id ASC
            """,
            (start, end),
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()
#重複タスク削除機能
def delete_a_task(
    a_task_id: int,
    db_path: Path = DEFAULT_DB_PATH,
) -> None:
    conn = connect(db_path)
    try:
        conn.execute(
            "DELETE FROM a_tasks WHERE id = ?",
            (a_task_id,),
        )
        conn.commit()
    finally:
        conn.close()


def delete_event(
    event_id: int,
    db_path: Path = DEFAULT_DB_PATH,
) -> None:
    conn = connect(db_path)
    try:
        conn.execute(
            "DELETE FROM events WHERE id = ?",
            (event_id,),
        )
        conn.commit()
    finally:
        conn.close()


def delete_daily_log(
    log_date: str,
    a_task_id: int,
    db_path: Path = DEFAULT_DB_PATH,
) -> None:
    conn = connect(db_path)
    try:
        conn.execute(
            """
            DELETE FROM daily_logs
            WHERE log_date = ? AND a_task_id = ?
            """,
            (log_date, a_task_id),
        )
        conn.commit()
    finally:
        conn.close()
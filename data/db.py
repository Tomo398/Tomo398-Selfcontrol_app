from __future__ import annotations

import sqlite3
from datetime import date, datetime, time
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


def update_a_task_total_minutes(
    a_task_id: int,
    new_total_minutes: int,
    db_path: Path = DEFAULT_DB_PATH,
) -> int:
    if new_total_minutes <= 0:
        raise ValueError("new_total_minutes must be >= 1")

    conn = connect(db_path)
    try:
        row = conn.execute(
            "SELECT id FROM a_tasks WHERE id = ?",
            (a_task_id,),
        ).fetchone()
        if row is None:
            raise ValueError(f"a_task_id not found: {a_task_id}")

        sum_row = conn.execute(
            "SELECT COALESCE(SUM(actual_minutes), 0) AS s FROM daily_logs WHERE a_task_id = ?",
            (a_task_id,),
        ).fetchone()
        done = int(sum_row["s"])
        remaining = max(int(new_total_minutes) - done, 0)

        conn.execute(
            """
            UPDATE a_tasks
            SET total_minutes = ?, remaining_minutes = ?
            WHERE id = ?
            """,
            (int(new_total_minutes), remaining, a_task_id),
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


def has_daily_log(
    log_date: str,
    a_task_id: int,
    db_path: Path = DEFAULT_DB_PATH,
) -> bool:
    conn = connect(db_path)
    try:
        row = conn.execute(
            """
            SELECT 1
            FROM daily_logs
            WHERE log_date = ? AND a_task_id = ?
            LIMIT 1
            """,
            (log_date, a_task_id),
        ).fetchone()
        return row is not None
    finally:
        conn.close()


def insert_routine_event(
    title: str,
    mode: str,
    start_time: str | None = None,       # "HH:MM", fixed_time用
    end_time: str | None = None,         # "HH:MM", fixed_time用
    duration_minutes: int | None = None, # duration_only用
    weekdays: str = "0,1,2,3,4,5,6",
    remind_start: int = 0,
    remind_end: int = 0,
    note: str = "",
    db_path: Path = DEFAULT_DB_PATH,
) -> int:
    if not title:
        raise ValueError("title is required")
    if mode not in ("fixed_time", "duration_only"):
        raise ValueError("mode must be 'fixed_time' or 'duration_only'")

    weekdays = _normalize_weekdays(weekdays)
    normalized_start_time: str | None = None
    normalized_end_time: str | None = None
    normalized_duration: int | None = None

    if mode == "fixed_time":
        start = _parse_hhmm(start_time)
        end = _parse_hhmm(end_time)
        if start is None or end is None:
            raise ValueError("start_time and end_time are required for fixed_time")
        if start >= end:
            raise ValueError("start_time must be before end_time")

        normalized_start_time = _format_hhmm(start)
        normalized_end_time = _format_hhmm(end)

    if mode == "duration_only":
        if duration_minutes is None or int(duration_minutes) <= 0:
            raise ValueError("duration_minutes must be > 0 for duration_only")
        normalized_duration = int(duration_minutes)

    conn = connect(db_path)
    try:
        cur = conn.execute(
            """
            INSERT INTO routine_events (
              title, mode, start_time, end_time, duration_minutes,
              weekdays, remind_start, remind_end, note
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                title,
                mode,
                normalized_start_time,
                normalized_end_time,
                normalized_duration,
                weekdays,
                remind_start,
                remind_end,
                note,
            ),
        )
        conn.commit()
        return int(cur.lastrowid)
    finally:
        conn.close()


def list_routine_events_for_date(
    target_date: str,     # "YYYY-MM-DD"
    db_path: Path = DEFAULT_DB_PATH,
) -> list[dict]:
    target = date.fromisoformat(target_date)
    target_weekday = target.weekday()

    conn = connect(db_path)
    try:
        rows = conn.execute(
            """
            SELECT
              id, title, mode, start_time, end_time, duration_minutes,
              weekdays, remind_start, remind_end, note
            FROM routine_events
            ORDER BY id ASC
            """
        ).fetchall()
    finally:
        conn.close()

    routine_events: list[dict] = []
    for row in rows:
        routine = dict(row)
        if not _weekday_applies(str(routine["weekdays"]), target_weekday):
            continue

        if routine["mode"] == "fixed_time":
            routine_events.append(
                {
                    "type": "C",
                    "source": "routine",
                    "routine_id": int(routine["id"]),
                    "mode": "fixed_time",
                    "title": routine["title"],
                    "start_dt": f'{target_date}T{routine["start_time"]}:00',
                    "end_dt": f'{target_date}T{routine["end_time"]}:00',
                    "remind_start": routine["remind_start"],
                    "remind_end": routine["remind_end"],
                    "note": routine["note"],
                }
            )
            continue

        routine_events.append(
            {
                "type": "C",
                "source": "routine",
                "routine_id": int(routine["id"]),
                "mode": "duration_only",
                "title": routine["title"],
                "duration_minutes": int(routine["duration_minutes"]),
                "note": routine["note"],
            }
        )

    return routine_events


def delete_routine_event(
    routine_event_id: int,
    db_path: Path = DEFAULT_DB_PATH,
) -> None:
    conn = connect(db_path)
    try:
        conn.execute(
            "DELETE FROM routine_events WHERE id = ?",
            (routine_event_id,),
        )
        conn.commit()
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


def _parse_hhmm(value: str | None) -> time | None:
    if value is None:
        return None

    try:
        return datetime.strptime(value.strip(), "%H:%M").time()
    except ValueError:
        return None


def _format_hhmm(value: time) -> str:
    return value.strftime("%H:%M")


def _normalize_weekdays(weekdays: str) -> str:
    parts = [part.strip() for part in weekdays.split(",") if part.strip()]
    if not parts:
        raise ValueError("weekdays is required")

    normalized = []
    for part in parts:
        try:
            weekday = int(part)
        except ValueError as exc:
            raise ValueError("weekdays must contain integers from 0 to 6") from exc

        if weekday < 0 or weekday > 6:
            raise ValueError("weekdays must contain integers from 0 to 6")

        normalized.append(str(weekday))

    return ",".join(normalized)


def _weekday_applies(weekdays: str, target_weekday: int) -> bool:
    parts = {part.strip() for part in weekdays.split(",") if part.strip()}
    return str(target_weekday) in parts


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

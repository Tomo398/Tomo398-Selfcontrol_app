from __future__ import annotations

import sqlite3
from datetime import date, datetime, time
from pathlib import Path

from typing import Optional, Iterable

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DB_PATH = PROJECT_ROOT / "data" / "app.db"
DEFAULT_SCHEMA_PATH = PROJECT_ROOT / "data" / "schema.sql"
A_TASK_STATUSES = {"active", "completed", "incomplete"}
A_TASK_SCALE_LABELS = {"weekly", "monthly", "yearly", "other"}


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
        _ensure_a_tasks_status_column(conn)
        _ensure_a_tasks_start_date_column(conn)
        _ensure_a_tasks_scale_label_column(conn)
        sql = schema_path.read_text(encoding="utf-8")
        conn.executescript(sql)
        _ensure_a_tasks_status_column(conn)
        _ensure_a_tasks_start_date_column(conn)
        _ensure_a_tasks_scale_label_column(conn)
        _ensure_a_task_candidates_table(conn)
        _ensure_settings_table(conn)
        conn.commit()
    finally:
        conn.close()


def insert_a_task(
    title: str,
    deadline_date: str,   # "YYYY-MM-DD"
    total_minutes: int,
    db_path: Path = DEFAULT_DB_PATH,
    start_date: str | None = None,   # "YYYY-MM-DD"
    task_scale_label: str = "other",
) -> int:
    if total_minutes < 0:
        raise ValueError("total_minutes must be >= 0")
    normalized_start_date, normalized_deadline_date = _normalize_a_task_date_range(
        start_date=start_date,
        deadline_date=deadline_date,
    )
    task_scale_label = _normalize_task_scale_label(task_scale_label)

    conn = connect(db_path)
    try:
        _ensure_a_tasks_start_date_column(conn)
        _ensure_a_tasks_scale_label_column(conn)
        cur = conn.execute(
            """
            INSERT INTO a_tasks (
              title, start_date, deadline_date, total_minutes,
              remaining_minutes, task_scale_label
            )
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                title,
                normalized_start_date,
                normalized_deadline_date,
                total_minutes,
                total_minutes,
                task_scale_label,
            ),
        )
        conn.commit()
        return int(cur.lastrowid)
    finally:
        conn.close()


def list_a_tasks(db_path: Path = DEFAULT_DB_PATH) -> list[dict]:
    conn = connect(db_path)
    try:
        _ensure_a_tasks_status_column(conn)
        _ensure_a_tasks_start_date_column(conn)
        _ensure_a_tasks_scale_label_column(conn)
        rows = conn.execute(
            """
            SELECT
              id, title, start_date, deadline_date, total_minutes,
              remaining_minutes, task_scale_label, status, created_at
            FROM a_tasks
            WHERE status = 'active'
            ORDER BY deadline_date ASC, id ASC
            """
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def list_expired_active_a_tasks(
    target_date: str,
    db_path: Path = DEFAULT_DB_PATH,
) -> list[dict]:
    date.fromisoformat(target_date)

    conn = connect(db_path)
    try:
        _ensure_a_tasks_status_column(conn)
        _ensure_a_tasks_start_date_column(conn)
        _ensure_a_tasks_scale_label_column(conn)
        rows = conn.execute(
            """
            SELECT
              id, title, start_date, deadline_date, total_minutes,
              remaining_minutes, task_scale_label, status, created_at
            FROM a_tasks
            WHERE status = 'active'
              AND deadline_date < ?
            ORDER BY deadline_date ASC, id ASC
            """,
            (target_date,),
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
        _ensure_a_tasks_status_column(conn)
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


def update_a_task_status(
    a_task_id: int,
    status: str,
    db_path: Path = DEFAULT_DB_PATH,
) -> None:
    if status not in A_TASK_STATUSES:
        raise ValueError("status must be active, completed, or incomplete")

    conn = connect(db_path)
    try:
        _ensure_a_tasks_status_column(conn)
        cur = conn.execute(
            "UPDATE a_tasks SET status = ? WHERE id = ?",
            (status, a_task_id),
        )
        if cur.rowcount == 0:
            raise ValueError(f"a_task_id not found: {a_task_id}")
        conn.commit()
    finally:
        conn.close()


def update_a_task_scale_label(
    a_task_id: int,
    task_scale_label: str,
    db_path: Path = DEFAULT_DB_PATH,
) -> None:
    task_scale_label = _normalize_task_scale_label(task_scale_label)

    conn = connect(db_path)
    try:
        _ensure_a_tasks_scale_label_column(conn)
        cur = conn.execute(
            "UPDATE a_tasks SET task_scale_label = ? WHERE id = ?",
            (task_scale_label, a_task_id),
        )
        if cur.rowcount == 0:
            raise ValueError(f"a_task_id not found: {a_task_id}")
        conn.commit()
    finally:
        conn.close()


def insert_a_task_candidate(
    title: str,
    memo: str = "",
    category: str = "",
    db_path: Path = DEFAULT_DB_PATH,
) -> int:
    title = title.strip()
    if not title:
        raise ValueError("title is required")

    conn = connect(db_path)
    try:
        _ensure_a_task_candidates_table(conn)
        cur = conn.execute(
            """
            INSERT INTO a_task_candidates (title, memo, category)
            VALUES (?, ?, ?)
            """,
            (title, memo.strip(), category.strip()),
        )
        conn.commit()
        return int(cur.lastrowid)
    finally:
        conn.close()


def list_a_task_candidates(db_path: Path = DEFAULT_DB_PATH) -> list[dict]:
    conn = connect(db_path)
    try:
        _ensure_a_task_candidates_table(conn)
        rows = conn.execute(
            """
            SELECT id, title, memo, category, is_converted, created_at
            FROM a_task_candidates
            ORDER BY is_converted ASC, created_at DESC, id DESC
            """
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def mark_a_task_candidate_converted(
    candidate_id: int,
    is_converted: bool = True,
    db_path: Path = DEFAULT_DB_PATH,
) -> None:
    conn = connect(db_path)
    try:
        _ensure_a_task_candidates_table(conn)
        cur = conn.execute(
            """
            UPDATE a_task_candidates
            SET is_converted = ?
            WHERE id = ?
            """,
            (1 if is_converted else 0, candidate_id),
        )
        if cur.rowcount == 0:
            raise ValueError(f"a_task_candidate_id not found: {candidate_id}")
        conn.commit()
    finally:
        conn.close()


def get_setting(
    key: str,
    default: str | None = None,
    db_path: Path = DEFAULT_DB_PATH,
) -> str | None:
    conn = connect(db_path)
    try:
        _ensure_settings_table(conn)
        row = conn.execute(
            "SELECT value FROM settings WHERE key = ?",
            (key,),
        ).fetchone()
        if row is None:
            return default
        return str(row["value"])
    finally:
        conn.close()


def set_setting(
    key: str,
    value: str,
    db_path: Path = DEFAULT_DB_PATH,
) -> None:
    conn = connect(db_path)
    try:
        _ensure_settings_table(conn)
        conn.execute(
            """
            INSERT INTO settings (key, value)
            VALUES (?, ?)
            ON CONFLICT(key) DO UPDATE SET
              value = excluded.value
            """,
            (key, value),
        )
        conn.commit()
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


def _ensure_a_tasks_status_column(conn: sqlite3.Connection) -> None:
    table = conn.execute(
        """
        SELECT name
        FROM sqlite_master
        WHERE type = 'table' AND name = 'a_tasks'
        """
    ).fetchone()
    if table is None:
        return

    columns = {
        str(row["name"])
        for row in conn.execute("PRAGMA table_info(a_tasks)").fetchall()
    }
    if "status" in columns:
        return

    conn.execute(
        "ALTER TABLE a_tasks ADD COLUMN status TEXT NOT NULL DEFAULT 'active'"
    )
    conn.commit()


def _ensure_a_tasks_start_date_column(conn: sqlite3.Connection) -> None:
    table = conn.execute(
        """
        SELECT name
        FROM sqlite_master
        WHERE type = 'table' AND name = 'a_tasks'
        """
    ).fetchone()
    if table is None:
        return

    columns = {
        str(row["name"])
        for row in conn.execute("PRAGMA table_info(a_tasks)").fetchall()
    }
    if "start_date" not in columns:
        conn.execute(
            "ALTER TABLE a_tasks ADD COLUMN start_date TEXT NOT NULL DEFAULT ''"
        )

    if "created_at" in columns:
        conn.execute(
            """
            UPDATE a_tasks
            SET start_date = COALESCE(NULLIF(substr(created_at, 1, 10), ''), deadline_date)
            WHERE start_date = ''
            """
        )
    else:
        conn.execute(
            """
            UPDATE a_tasks
            SET start_date = deadline_date
            WHERE start_date = ''
            """
        )
    conn.commit()


def _ensure_a_tasks_scale_label_column(conn: sqlite3.Connection) -> None:
    table = conn.execute(
        """
        SELECT name
        FROM sqlite_master
        WHERE type = 'table' AND name = 'a_tasks'
        """
    ).fetchone()
    if table is None:
        return

    columns = {
        str(row["name"])
        for row in conn.execute("PRAGMA table_info(a_tasks)").fetchall()
    }
    if "task_scale_label" not in columns:
        conn.execute(
            """
            ALTER TABLE a_tasks
            ADD COLUMN task_scale_label TEXT NOT NULL DEFAULT 'other'
            """
        )

    conn.execute(
        """
        UPDATE a_tasks
        SET task_scale_label = 'other'
        WHERE task_scale_label NOT IN ('weekly', 'monthly', 'yearly', 'other')
        """
    )
    conn.commit()


def _ensure_settings_table(conn: sqlite3.Connection) -> None:
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS settings (
          key TEXT PRIMARY KEY,
          value TEXT NOT NULL
        )
        """
    )
    conn.commit()


def _ensure_a_task_candidates_table(conn: sqlite3.Connection) -> None:
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS a_task_candidates (
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          title TEXT NOT NULL,
          memo TEXT NOT NULL DEFAULT '',
          category TEXT NOT NULL DEFAULT '',
          is_converted INTEGER NOT NULL DEFAULT 0 CHECK(is_converted IN (0, 1)),
          created_at TEXT NOT NULL DEFAULT (datetime('now'))
        )
        """
    )
    conn.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_task_candidates_converted
        ON a_task_candidates(is_converted, created_at)
        """
    )
    conn.commit()


def _normalize_a_task_date_range(
    start_date: str | None,
    deadline_date: str,
) -> tuple[str, str]:
    deadline = date.fromisoformat(deadline_date)
    start = date.fromisoformat(start_date) if start_date else date.today()
    if start > deadline:
        raise ValueError("start_date must be on or before deadline_date")
    return start.isoformat(), deadline.isoformat()


def _normalize_task_scale_label(task_scale_label: str) -> str:
    label = task_scale_label.strip()
    if label not in A_TASK_SCALE_LABELS:
        raise ValueError("task_scale_label must be weekly, monthly, yearly, or other")
    return label


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

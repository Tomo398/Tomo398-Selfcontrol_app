import sqlite3

import pytest

from data.db import (
    has_daily_log,
    init_db,
    insert_a_task,
    list_a_tasks,
    list_expired_active_a_tasks,
    update_a_task_total_minutes,
    update_a_task_status,
    upsert_daily_log,
)


def test_update_a_task_total_minutes_recomputes_remaining_when_total_increases(tmp_path) -> None:
    db_path = tmp_path / "app.db"
    init_db(db_path=db_path)
    task_id = insert_a_task(
        title="Long task",
        deadline_date="2026-06-30",
        total_minutes=1200,
        db_path=db_path,
    )
    upsert_daily_log(
        log_date="2026-04-20",
        a_task_id=task_id,
        actual_minutes=120,
        db_path=db_path,
    )

    remaining = update_a_task_total_minutes(task_id, 1800, db_path=db_path)

    assert remaining == 1680
    [task] = list_a_tasks(db_path=db_path)
    assert task["total_minutes"] == 1800
    assert task["remaining_minutes"] == 1680


def test_insert_a_task_saves_start_date(tmp_path) -> None:
    db_path = tmp_path / "app.db"
    init_db(db_path=db_path)

    task_id = insert_a_task(
        title="Scheduled task",
        start_date="2026-05-01",
        deadline_date="2026-05-10",
        total_minutes=300,
        db_path=db_path,
    )

    [task] = list_a_tasks(db_path=db_path)
    assert task["id"] == task_id
    assert task["start_date"] == "2026-05-01"
    assert task["deadline_date"] == "2026-05-10"


def test_insert_a_task_rejects_start_date_after_deadline(tmp_path) -> None:
    db_path = tmp_path / "app.db"
    init_db(db_path=db_path)

    with pytest.raises(ValueError):
        insert_a_task(
            title="Bad range",
            start_date="2026-05-11",
            deadline_date="2026-05-10",
            total_minutes=300,
            db_path=db_path,
        )


def test_update_a_task_total_minutes_clamps_remaining_to_zero(tmp_path) -> None:
    db_path = tmp_path / "app.db"
    init_db(db_path=db_path)
    task_id = insert_a_task(
        title="Long task",
        deadline_date="2026-06-30",
        total_minutes=1200,
        db_path=db_path,
    )
    upsert_daily_log(
        log_date="2026-04-20",
        a_task_id=task_id,
        actual_minutes=120,
        db_path=db_path,
    )

    remaining = update_a_task_total_minutes(task_id, 100, db_path=db_path)

    assert remaining == 0
    [task] = list_a_tasks(db_path=db_path)
    assert task["total_minutes"] == 100
    assert task["remaining_minutes"] == 0


def test_update_a_task_total_minutes_validates_input(tmp_path) -> None:
    db_path = tmp_path / "app.db"
    init_db(db_path=db_path)

    with pytest.raises(ValueError):
        update_a_task_total_minutes(1, 0, db_path=db_path)

    with pytest.raises(ValueError):
        update_a_task_total_minutes(999, 100, db_path=db_path)


def test_has_daily_log_treats_zero_minute_log_as_existing(tmp_path) -> None:
    db_path = tmp_path / "app.db"
    init_db(db_path=db_path)
    task_id = insert_a_task(
        title="Long task",
        deadline_date="2026-06-30",
        total_minutes=1200,
        db_path=db_path,
    )

    assert has_daily_log("2026-04-20", task_id, db_path=db_path) is False

    upsert_daily_log(
        log_date="2026-04-20",
        a_task_id=task_id,
        actual_minutes=0,
        reflection="未実施",
        db_path=db_path,
    )

    assert has_daily_log("2026-04-20", task_id, db_path=db_path) is True


def test_update_a_task_status_hides_closed_tasks_from_active_list(tmp_path) -> None:
    db_path = tmp_path / "app.db"
    init_db(db_path=db_path)
    completed_id = insert_a_task(
        title="Completed",
        start_date="2026-04-20",
        deadline_date="2026-04-20",
        total_minutes=120,
        db_path=db_path,
    )
    incomplete_id = insert_a_task(
        title="Incomplete",
        start_date="2026-04-21",
        deadline_date="2026-04-21",
        total_minutes=120,
        db_path=db_path,
    )
    active_id = insert_a_task(
        title="Active",
        start_date="2026-04-22",
        deadline_date="2026-04-22",
        total_minutes=120,
        db_path=db_path,
    )

    update_a_task_status(completed_id, "completed", db_path=db_path)
    update_a_task_status(incomplete_id, "incomplete", db_path=db_path)

    assert [task["id"] for task in list_a_tasks(db_path=db_path)] == [active_id]


def test_list_expired_active_a_tasks_returns_only_active_expired_tasks(tmp_path) -> None:
    db_path = tmp_path / "app.db"
    init_db(db_path=db_path)
    expired_id = insert_a_task(
        title="Expired",
        start_date="2026-04-18",
        deadline_date="2026-04-19",
        total_minutes=120,
        db_path=db_path,
    )
    today_deadline_id = insert_a_task(
        title="Due today",
        start_date="2026-04-20",
        deadline_date="2026-04-20",
        total_minutes=120,
        db_path=db_path,
    )
    closed_expired_id = insert_a_task(
        title="Closed expired",
        start_date="2026-04-18",
        deadline_date="2026-04-18",
        total_minutes=120,
        db_path=db_path,
    )
    update_a_task_status(closed_expired_id, "completed", db_path=db_path)

    expired_tasks = list_expired_active_a_tasks("2026-04-20", db_path=db_path)

    assert [task["id"] for task in expired_tasks] == [expired_id]
    assert today_deadline_id in [task["id"] for task in list_a_tasks(db_path=db_path)]


def test_update_a_task_status_validates_input(tmp_path) -> None:
    db_path = tmp_path / "app.db"
    init_db(db_path=db_path)

    with pytest.raises(ValueError):
        update_a_task_status(1, "done", db_path=db_path)

    with pytest.raises(ValueError):
        update_a_task_status(999, "completed", db_path=db_path)


def test_init_db_adds_status_column_to_existing_a_tasks_table(tmp_path) -> None:
    db_path = tmp_path / "app.db"
    conn = sqlite3.connect(db_path)
    try:
        conn.execute(
            """
            CREATE TABLE a_tasks (
              id INTEGER PRIMARY KEY AUTOINCREMENT,
              title TEXT NOT NULL,
              deadline_date TEXT NOT NULL,
              total_minutes INTEGER NOT NULL CHECK(total_minutes >= 0),
              remaining_minutes INTEGER NOT NULL CHECK(remaining_minutes >= 0),
              created_at TEXT NOT NULL DEFAULT (datetime('now'))
            )
            """
        )
        conn.execute(
            """
            INSERT INTO a_tasks (title, deadline_date, total_minutes, remaining_minutes)
            VALUES ('Old task', '2026-04-20', 120, 120)
            """
        )
        conn.commit()
    finally:
        conn.close()

    init_db(db_path=db_path)

    [task] = list_a_tasks(db_path=db_path)
    assert task["status"] == "active"
    assert task["start_date"] == task["created_at"][:10]

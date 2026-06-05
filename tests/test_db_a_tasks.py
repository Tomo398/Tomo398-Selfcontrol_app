import pytest

from data.db import (
    has_daily_log,
    init_db,
    insert_a_task,
    list_a_tasks,
    update_a_task_total_minutes,
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

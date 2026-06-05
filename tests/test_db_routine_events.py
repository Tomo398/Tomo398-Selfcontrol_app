import pytest

from data.db import (
    delete_routine_event,
    init_db,
    insert_routine_event,
    list_routine_events_for_date,
)


def test_list_routine_events_for_date_expands_matching_weekday(tmp_path) -> None:
    db_path = tmp_path / "app.db"
    init_db(db_path=db_path)

    fixed_id = insert_routine_event(
        title="Sleep",
        mode="fixed_time",
        start_time="07:00",
        end_time="08:00",
        weekdays="0",
        remind_start=1,
        note="morning",
        db_path=db_path,
    )
    duration_id = insert_routine_event(
        title="Housework",
        mode="duration_only",
        duration_minutes=45,
        weekdays="0",
        note="anytime",
        db_path=db_path,
    )

    assert list_routine_events_for_date("2026-04-20", db_path=db_path) == [
        {
            "type": "C",
            "source": "routine",
            "routine_id": fixed_id,
            "mode": "fixed_time",
            "title": "Sleep",
            "start_dt": "2026-04-20T07:00:00",
            "end_dt": "2026-04-20T08:00:00",
            "remind_start": 1,
            "remind_end": 0,
            "note": "morning",
        },
        {
            "type": "C",
            "source": "routine",
            "routine_id": duration_id,
            "mode": "duration_only",
            "title": "Housework",
            "duration_minutes": 45,
            "note": "anytime",
        },
    ]
    assert list_routine_events_for_date("2026-04-21", db_path=db_path) == []


def test_delete_routine_event_removes_rule(tmp_path) -> None:
    db_path = tmp_path / "app.db"
    init_db(db_path=db_path)

    routine_id = insert_routine_event(
        title="Meal",
        mode="duration_only",
        duration_minutes=30,
        db_path=db_path,
    )
    delete_routine_event(routine_id, db_path=db_path)

    assert list_routine_events_for_date("2026-04-20", db_path=db_path) == []


def test_insert_routine_event_validates_mode_requirements(tmp_path) -> None:
    db_path = tmp_path / "app.db"
    init_db(db_path=db_path)

    with pytest.raises(ValueError):
        insert_routine_event(
            title="Bad fixed",
            mode="fixed_time",
            start_time="10:00",
            end_time="09:00",
            db_path=db_path,
        )

    with pytest.raises(ValueError):
        insert_routine_event(
            title="Bad duration",
            mode="duration_only",
            duration_minutes=0,
            db_path=db_path,
        )

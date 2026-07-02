import pytest

from data.db import (
    delete_schedule_exception,
    init_db,
    insert_schedule_exception,
    list_schedule_exceptions,
    list_schedule_exceptions_for_date,
)


def test_schedule_exception_can_be_saved_listed_and_matched_by_date(tmp_path) -> None:
    db_path = tmp_path / "app.db"
    init_db(db_path=db_path)

    exception_id = insert_schedule_exception(
        title="Trip",
        start_date="2026-04-20",
        end_date="2026-04-22",
        note="Away",
        db_path=db_path,
    )

    [exception] = list_schedule_exceptions(db_path=db_path)
    assert exception["id"] == exception_id
    assert exception["title"] == "Trip"
    assert exception["start_date"] == "2026-04-20"
    assert exception["end_date"] == "2026-04-22"
    assert exception["note"] == "Away"

    assert [item["id"] for item in list_schedule_exceptions_for_date("2026-04-19", db_path=db_path)] == []
    assert [item["id"] for item in list_schedule_exceptions_for_date("2026-04-20", db_path=db_path)] == [exception_id]
    assert [item["id"] for item in list_schedule_exceptions_for_date("2026-04-22", db_path=db_path)] == [exception_id]
    assert [item["id"] for item in list_schedule_exceptions_for_date("2026-04-23", db_path=db_path)] == []


def test_schedule_exception_rejects_start_after_end(tmp_path) -> None:
    db_path = tmp_path / "app.db"
    init_db(db_path=db_path)

    with pytest.raises(ValueError):
        insert_schedule_exception(
            start_date="2026-04-22",
            end_date="2026-04-20",
            db_path=db_path,
        )


def test_delete_schedule_exception_removes_exception(tmp_path) -> None:
    db_path = tmp_path / "app.db"
    init_db(db_path=db_path)
    exception_id = insert_schedule_exception(
        start_date="2026-04-20",
        end_date="2026-04-20",
        db_path=db_path,
    )

    delete_schedule_exception(exception_id, db_path=db_path)

    assert list_schedule_exceptions(db_path=db_path) == []

    with pytest.raises(ValueError):
        delete_schedule_exception(exception_id, db_path=db_path)

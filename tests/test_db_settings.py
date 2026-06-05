from data.db import get_setting, init_db, set_setting


def test_get_setting_returns_default_when_missing(tmp_path) -> None:
    db_path = tmp_path / "app.db"
    init_db(db_path=db_path)

    assert get_setting("missing", "08:00", db_path=db_path) == "08:00"


def test_set_setting_inserts_and_updates_value(tmp_path) -> None:
    db_path = tmp_path / "app.db"
    init_db(db_path=db_path)

    set_setting("morning_check_time", "08:00", db_path=db_path)
    assert get_setting("morning_check_time", db_path=db_path) == "08:00"

    set_setting("morning_check_time", "09:00", db_path=db_path)
    assert get_setting("morning_check_time", db_path=db_path) == "09:00"

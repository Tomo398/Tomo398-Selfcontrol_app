import sqlite3

import pytest

from data.db import (
    init_db,
    insert_a_task_candidate,
    list_a_task_candidates,
    mark_a_task_candidate_converted,
)


def test_a_task_candidate_can_be_saved_listed_and_marked_converted(tmp_path) -> None:
    db_path = tmp_path / "app.db"
    init_db(db_path=db_path)

    candidate_id = insert_a_task_candidate(
        title="Research idea",
        memo="Read two papers first",
        category="research",
        db_path=db_path,
    )

    [candidate] = list_a_task_candidates(db_path=db_path)
    assert candidate["id"] == candidate_id
    assert candidate["title"] == "Research idea"
    assert candidate["memo"] == "Read two papers first"
    assert candidate["category"] == "research"
    assert candidate["is_converted"] == 0
    assert candidate["created_at"]

    mark_a_task_candidate_converted(candidate_id, db_path=db_path)

    [candidate] = list_a_task_candidates(db_path=db_path)
    assert candidate["is_converted"] == 1


def test_insert_a_task_candidate_requires_title(tmp_path) -> None:
    db_path = tmp_path / "app.db"
    init_db(db_path=db_path)

    with pytest.raises(ValueError):
        insert_a_task_candidate(title="", db_path=db_path)


def test_init_db_adds_a_task_candidates_table_to_existing_database(tmp_path) -> None:
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
        conn.commit()
    finally:
        conn.close()

    init_db(db_path=db_path)

    candidate_id = insert_a_task_candidate(
        title="Later task",
        db_path=db_path,
    )
    [candidate] = list_a_task_candidates(db_path=db_path)
    assert candidate["id"] == candidate_id

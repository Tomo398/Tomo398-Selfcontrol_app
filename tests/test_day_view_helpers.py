from ui.day_view import _split_expired_tasks_for_results


def test_split_expired_tasks_moves_week_old_tasks_to_results() -> None:
    recent_task = {
        "id": 1,
        "title": "Recent expired",
        "deadline_date": "2026-04-14",
        "remaining_minutes": 30,
    }
    result_task = {
        "id": 2,
        "title": "Week old expired",
        "deadline_date": "2026-04-13",
        "remaining_minutes": 30,
    }

    recent_tasks, result_tasks = _split_expired_tasks_for_results(
        [recent_task, result_task],
        "2026-04-20",
    )

    assert recent_tasks == [recent_task]
    assert result_tasks == [result_task]

from datetime import datetime

from core.scheduler import (
    allocate_task_to_free_blocks,
    allocate_tasks_to_free_blocks,
    build_busy_blocks,
    build_capacity_summary,
    build_free_blocks,
    compute_daily_target_rounded_minutes,
)


def dt(hour: int, minute: int = 0) -> datetime:
    return datetime(2026, 4, 20, hour, minute)


def test_compute_daily_target_rounded_minutes_rounds_up_to_granularity() -> None:
    assert (
        compute_daily_target_rounded_minutes(
            remaining_minutes=20,
            deadline_date="2026-04-23",
            today="2026-04-20",
        )
        == 15
    )


def test_build_busy_blocks_sorts_events_and_skips_invalid_ranges() -> None:
    events = [
        {
            "start_dt": "2026-04-20T13:00:00",
            "end_dt": "2026-04-20T14:00:00",
        },
        {
            "start_dt": "2026-04-20T09:00:00",
            "end_dt": "2026-04-20T10:00:00",
        },
        {
            "start_dt": "2026-04-20T11:00:00",
            "end_dt": "2026-04-20T11:00:00",
        },
    ]

    assert build_busy_blocks(events) == [
        (dt(9), dt(10)),
        (dt(13), dt(14)),
    ]


def test_build_free_blocks_subtracts_merged_busy_blocks() -> None:
    busy_blocks = [
        (dt(9), dt(10)),
        (dt(9, 30), dt(11)),
        (dt(13), dt(14)),
    ]

    assert build_free_blocks(
        target_date="2026-04-20",
        busy_blocks=busy_blocks,
        available_start="08:00",
        available_end="15:00",
    ) == [
        (dt(8), dt(9)),
        (dt(11), dt(13)),
        (dt(14), dt(15)),
    ]


def test_build_capacity_summary_subtracts_duration_only_cost() -> None:
    free_blocks = [
        (dt(8), dt(10)),
        (dt(13), dt(14)),
    ]
    duration_only_events = [
        {"mode": "duration_only", "duration_minutes": 90},
        {"mode": "duration_only", "duration_minutes": 30},
    ]
    tasks_with_targets = [
        {"daily_target_minutes": 240},
        {"daily_target_minutes": 30},
    ]
    allocations = [
        {"minutes": 60},
        {"minutes": 30},
    ]

    assert build_capacity_summary(
        free_blocks=free_blocks,
        duration_only_events=duration_only_events,
        tasks_with_targets=tasks_with_targets,
        allocations=allocations,
    ) == {
        "fixed_free_minutes": 180,
        "floating_c_minutes": 120,
        "effective_work_minutes": 60,
        "total_a_target_minutes": 270,
        "surplus_minutes": -210,
        "is_over_capacity": True,
        "allocated_a_minutes": 90,
    }


def test_allocate_task_to_free_blocks_uses_free_blocks_in_order() -> None:
    task = {"id": 1, "title": "Report"}
    free_blocks = [
        (dt(8), dt(8, 20)),
        (dt(9), dt(10)),
        (dt(10, 30), dt(12)),
    ]

    # MVP rule: ignore blocks shorter than the granularity and allocate from the front.
    assert allocate_task_to_free_blocks(
        task=task,
        free_blocks=free_blocks,
        target_minutes=75,
    ) == [
        {
            "a_task_id": 1,
            "title": "Report",
            "start": "2026-04-20T08:00:00",
            "end": "2026-04-20T08:15:00",
            "minutes": 15,
        },
        {
            "a_task_id": 1,
            "title": "Report",
            "start": "2026-04-20T09:00:00",
            "end": "2026-04-20T10:00:00",
            "minutes": 60,
        },
    ]


def test_allocate_tasks_to_free_blocks_allocates_by_deadline_order() -> None:
    tasks = [
        {
            "id": 1,
            "title": "Later",
            "deadline_date": "2026-04-25",
            "remaining_minutes": 300,
        },
        {
            "id": 2,
            "title": "Sooner",
            "deadline_date": "2026-04-21",
            "remaining_minutes": 90,
        },
    ]

    assert allocate_tasks_to_free_blocks(
        tasks=tasks,
        free_blocks=[(dt(8), dt(10))],
        today="2026-04-20",
    ) == [
        {
            "a_task_id": 2,
            "title": "Sooner",
            "start": "2026-04-20T08:00:00",
            "end": "2026-04-20T08:45:00",
            "minutes": 45,
        },
        {
            "a_task_id": 1,
            "title": "Later",
            "start": "2026-04-20T08:45:00",
            "end": "2026-04-20T09:45:00",
            "minutes": 60,
        },
    ]

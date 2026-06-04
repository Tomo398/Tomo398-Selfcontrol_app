from data.db import list_a_tasks, list_events_by_date
from core.scheduler import (
    build_busy_blocks,
    build_free_blocks,
    allocate_tasks_to_free_blocks,
    attach_daily_targets_to_tasks,
    format_blocks,
)

today = "2026-04-20"

events = list_events_by_date(today)
busy = build_busy_blocks(events)
free = build_free_blocks(today, busy)

tasks = list_a_tasks()
tasks_with_targets = attach_daily_targets_to_tasks(tasks, today=today)



allocations = allocate_tasks_to_free_blocks(
    tasks=tasks,
    free_blocks=free,
    today=today,
)

print("events:")
print(events)

print("\nfree blocks:")
print(format_blocks(free))

print("\ntasks with targets:")
print(tasks_with_targets)

print("\nallocations:")
print(allocations)
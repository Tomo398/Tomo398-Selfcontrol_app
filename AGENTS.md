# AGENTS.md

## Project
Python + PySide6 desktop app for rule-based self-management / schedule planning.

## Goal
Build an MVP within 40-80 hours.

The app manages:
- A tasks: deadline-based tasks requiring preparation time.
- B events: one-off or sudden events that occupy time but do not require preparation.
- C events: recurring life routines such as sleep, meals, commuting, housework.

Main MVP loop:
1. Register A tasks with total required minutes and deadline.
2. Register B/C events with fixed start/end times.
3. Log actual minutes spent on A tasks each day.
4. Recompute remaining minutes.
5. Compute daily target minutes for each A task.
6. Build free time blocks by subtracting B/C events.
7. Allocate A tasks into free blocks in deadline order.
8. Later: display this in a PySide6 Day view and add reminders.

## Current tech stack
- Python
- PySide6 for desktop UI
- SQLite via Python standard sqlite3
- 30-minute scheduling granularity
- Local-only MVP
- VS Code

## Important design decisions
- A tasks are stored in `a_tasks`.
- B/C events are stored in `events`.
- A tasks are not stored as fixed events because they represent required work time, not fixed appointments.
- Actual work logs are stored in `daily_logs`.
- Remaining minutes are recomputed from total minutes minus sum of logs.
- Dates are stored as ISO strings:
  - date: YYYY-MM-DD
  - datetime: YYYY-MM-DDTHH:MM:SS
- MVP uses simple deadline-order allocation.
- Do not implement complex optimization yet.
- Do not build Year/Month/Week UI yet.
- Prioritize Day view first.
- marimo/Jupyter may be used only for testing/experiments, not as the production app.

## Current implemented files
- `data/schema.sql`
- `data/db.py`
- `core/scheduler.py`
- `check_schedule.py`

## Current working features
- Initialize SQLite DB.
- Insert/list/delete A tasks.
- Insert/list/delete B/C events.
- Upsert daily logs.
- Recompute remaining minutes.
- Compute daily target minutes rounded to 30 minutes.
- Build busy blocks from B/C events.
- Build free blocks.
- Allocate multiple A tasks into free blocks in deadline order.

## Current test state
Running:

```bash
python check_schedule.py
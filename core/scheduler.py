from __future__ import annotations

from datetime import date, datetime, time, timedelta

TimeBlock = tuple[datetime, datetime]


def parse_date(d: str) -> date:
    # DBでは日付を "YYYY-MM-DD" 形式の文字列で持つ。
    return date.fromisoformat(d)


def days_inclusive(today: date, deadline: date) -> int:
    """
    今日を含めて締切日まで何日あるか。
    例: today=4/20, deadline=4/20 => 1日
    """
    return (deadline - today).days + 1


def compute_daily_target_minutes(
    remaining_minutes: int,
    deadline_date: str,
    today: str | None = None,
) -> int:
    """
    MVP版: daily_target = ceil(remaining / remaining_days_inclusive)
    """
    if remaining_minutes < 0:
        raise ValueError("remaining_minutes must be >= 0")

    d_deadline = parse_date(deadline_date)
    d_today = parse_date(today) if today else date.today()

    remaining_days = days_inclusive(d_today, d_deadline)
    if remaining_days <= 0:
        # 期限切れ：今日に全部寄せる（MVPの割り切り）
        return remaining_minutes

    # ceil(a/b) = (a + b - 1) // b
    return (remaining_minutes + remaining_days - 1) // remaining_days

def round_up_to_granularity(minutes: int, granularity: int = 30) -> int:
    """
    minutes を granularity 分単位で切り上げる。
    例:
      1〜30  -> 30
      31〜60 -> 60
      0      -> 0
    """
    if minutes < 0:
        raise ValueError("minutes must be >= 0")
    if granularity <= 0:
        raise ValueError("granularity must be > 0")

    if minutes == 0:
        return 0

    return ((minutes + granularity - 1) // granularity) * granularity

def compute_daily_target_rounded_minutes(
    remaining_minutes: int,
    deadline_date: str,
    today: str | None = None,
    granularity: int = 30,
) -> int:
    """
    日割りした推奨時間を30分単位に切り上げる。
    """
    raw = compute_daily_target_minutes(
        remaining_minutes=remaining_minutes,
        deadline_date=deadline_date,
        today=today,
    )
    return round_up_to_granularity(raw, granularity)


def attach_daily_targets_to_tasks(
    tasks: list[dict],
    today: str | None = None,
    granularity: int = 30,
) -> list[dict]:
    """
    list_a_tasks() の結果に daily_target_minutes を付ける。
    DBは更新しない。表示・確認用。
    """
    result = []

    for task in tasks:
        task_with_target = dict(task)
        task_with_target["daily_target_minutes"] = compute_daily_target_rounded_minutes(
            remaining_minutes=int(task["remaining_minutes"]),
            deadline_date=str(task["deadline_date"]),
            today=today,
            granularity=granularity,
        )
        result.append(task_with_target)

    return result


def parse_datetime(dt: str) -> datetime:
    # DBでは日時を "YYYY-MM-DDTHH:MM:SS" 形式の文字列で持つ。
    return datetime.fromisoformat(dt)


def day_start(target_date: str) -> datetime:
    d = date.fromisoformat(target_date)
    return datetime.combine(d, time(0, 0))


def day_end(target_date: str) -> datetime:
    d = date.fromisoformat(target_date)
    return datetime.combine(d, time(23, 59, 59))


def build_busy_blocks(events: list[dict]) -> list[TimeBlock]:
    """
    B/C予定から埋まっている時間帯を作る。
    """
    blocks = []

    for event in events:
        start = parse_datetime(event["start_dt"])
        end = parse_datetime(event["end_dt"])

        if start >= end:
            continue

        blocks.append((start, end))

    blocks.sort(key=lambda x: x[0])
    return blocks


def merge_blocks(
    blocks: list[TimeBlock],
) -> list[TimeBlock]:
    """
    重なっている予定を結合する。
    例:
      10:00-11:00
      10:30-12:00
    => 10:00-12:00
    """
    if not blocks:
        return []

    blocks = sorted(blocks, key=lambda x: x[0])
    merged = [blocks[0]]

    for start, end in blocks[1:]:
        last_start, last_end = merged[-1]

        if start <= last_end:
            merged[-1] = (last_start, max(last_end, end))
        else:
            merged.append((start, end))

    return merged


def build_free_blocks(
    target_date: str,
    busy_blocks: list[TimeBlock],
    available_start: str = "00:00",
    available_end: str = "23:59",
) -> list[TimeBlock]:
    """
    可処分時間帯からbusy_blocksを引いてfree_blocksを作る。
    available_start/end は "HH:MM"
    """
    d = date.fromisoformat(target_date)

    start_h, start_m = map(int, available_start.split(":"))
    end_h, end_m = map(int, available_end.split(":"))

    available_s = datetime.combine(d, time(start_h, start_m))
    available_e = datetime.combine(d, time(end_h, end_m))

    busy_blocks = merge_blocks(busy_blocks)

    free = []
    cursor = available_s

    for busy_s, busy_e in busy_blocks:
        # 可処分時間の端で切り詰めてから差し引く。
        busy_s = max(busy_s, available_s)
        busy_e = min(busy_e, available_e)

        if busy_e <= available_s or busy_s >= available_e:
            continue

        if cursor < busy_s:
            free.append((cursor, busy_s))

        cursor = max(cursor, busy_e)

    if cursor < available_e:
        free.append((cursor, available_e))

    return free


def format_blocks(
    blocks: list[TimeBlock],
) -> list[dict]:
    """
    表示確認用。
    """
    return [
        {
            "start": s.strftime("%Y-%m-%dT%H:%M:%S"),
            "end": e.strftime("%Y-%m-%dT%H:%M:%S"),
            "minutes": int((e - s).total_seconds() // 60),
        }
        for s, e in blocks
    ]


def total_block_minutes(blocks: list[TimeBlock]) -> int:
    """
    TimeBlockの合計分数を返す。
    """
    return sum(int((end - start).total_seconds() // 60) for start, end in blocks)


def total_duration_only_minutes(routine_events: list[dict]) -> int:
    """
    時間未指定C(duration_only)の合計分数を返す。
    """
    total = 0

    for event in routine_events:
        if event.get("mode") != "duration_only":
            continue

        minutes = int(event.get("duration_minutes", 0))
        if minutes > 0:
            total += minutes

    return total


def total_daily_target_minutes(tasks: list[dict]) -> int:
    """
    daily_target_minutes付きAタスクの今日の推奨合計を返す。
    """
    return sum(int(task.get("daily_target_minutes", 0)) for task in tasks)


def total_allocation_minutes(allocations: list[dict]) -> int:
    """
    A割当結果の合計分数を返す。
    """
    return sum(int(allocation.get("minutes", 0)) for allocation in allocations)


def build_capacity_summary(
    free_blocks: list[TimeBlock],
    duration_only_events: list[dict],
    tasks_with_targets: list[dict],
    allocations: list[dict] | None = None,
) -> dict:
    """
    fixed_time予定を引いた空き時間から、時間未指定Cを固定コストとして差し引く。
    duration_only Cはまだ時刻へ自動配置しない。
    """
    fixed_free_minutes = total_block_minutes(free_blocks)
    floating_c_minutes = total_duration_only_minutes(duration_only_events)
    effective_work_minutes = max(fixed_free_minutes - floating_c_minutes, 0)
    total_a_target_minutes = total_daily_target_minutes(tasks_with_targets)
    surplus_minutes = effective_work_minutes - total_a_target_minutes

    summary = {
        "fixed_free_minutes": fixed_free_minutes,
        "floating_c_minutes": floating_c_minutes,
        "effective_work_minutes": effective_work_minutes,
        "total_a_target_minutes": total_a_target_minutes,
        "surplus_minutes": surplus_minutes,
        "is_over_capacity": surplus_minutes < 0,
    }

    if allocations is not None:
        summary["allocated_a_minutes"] = total_allocation_minutes(allocations)

    return summary


def subtract_busy_from_free_blocks(
    free_blocks: list[TimeBlock],
    busy_blocks: list[TimeBlock],
) -> list[TimeBlock]:
    """
    既存のfree_blocksから、追加のbusy_blocksを引く。
    複数Aタスクを順番に割り当てるときに使う。
    """
    result = free_blocks[:]

    for busy_s, busy_e in busy_blocks:
        new_result = []

        for free_s, free_e in result:
            # busyとfreeが重ならない
            if busy_e <= free_s or busy_s >= free_e:
                new_result.append((free_s, free_e))
                continue

            # busyの前に空きが残る
            if free_s < busy_s:
                new_result.append((free_s, busy_s))

            # busyの後に空きが残る
            if busy_e < free_e:
                new_result.append((busy_e, free_e))

        result = new_result

    return result

def allocate_task_to_free_blocks(
    task: dict,
    free_blocks: list[TimeBlock],
    target_minutes: int,
    granularity: int = 30,
) -> list[dict]:
    """
    1つのAタスクの推奨分をfree_blocksに前から順に割り当てる。
    MVPでは最適化しない。空いているところに前詰めするだけ。
    """
    if target_minutes < 0:
        raise ValueError("target_minutes must be >= 0")

    target_minutes = round_up_to_granularity(target_minutes, granularity)

    allocations = []
    remaining = target_minutes

    for block_start, block_end in free_blocks:
        if remaining <= 0:
            break

        block_minutes = int((block_end - block_start).total_seconds() // 60)

        # 30分未満の空きは捨てる
        usable_minutes = (block_minutes // granularity) * granularity

        if usable_minutes <= 0:
            continue

        use_minutes = min(remaining, usable_minutes)

        alloc_start = block_start
        alloc_end = alloc_start + timedelta(minutes=use_minutes)

        allocations.append(
            {
                "a_task_id": task["id"],
                "title": task["title"],
                "start": alloc_start.strftime("%Y-%m-%dT%H:%M:%S"),
                "end": alloc_end.strftime("%Y-%m-%dT%H:%M:%S"),
                "minutes": use_minutes,
            }
        )

        remaining -= use_minutes

    return allocations

def allocate_tasks_to_free_blocks(
    tasks: list[dict],
    free_blocks: list[TimeBlock],
    today: str,
    granularity: int = 30,
) -> list[dict]:
    """
    複数Aタスクを締切が近い順にfree_blocksへ割り当てる。
    MVPでは最適化しない。前から順に詰めるだけ。
    """
    allocations = []
    current_free_blocks = free_blocks[:]

    sorted_tasks = sorted(
        tasks,
        key=lambda t: (str(t["deadline_date"]), int(t["id"]))
    )

    for task in sorted_tasks:
        target_minutes = compute_daily_target_rounded_minutes(
            remaining_minutes=int(task["remaining_minutes"]),
            deadline_date=str(task["deadline_date"]),
            today=today,
            granularity=granularity,
        )

        if target_minutes <= 0:
            continue

        task_allocations = allocate_task_to_free_blocks(
            task=task,
            free_blocks=current_free_blocks,
            target_minutes=target_minutes,
            granularity=granularity,
        )

        allocations.extend(task_allocations)

        allocated_busy = [
            (parse_datetime(a["start"]), parse_datetime(a["end"]))
            for a in task_allocations
        ]

        current_free_blocks = subtract_busy_from_free_blocks(
            current_free_blocks,
            allocated_busy,
        )

    return allocations

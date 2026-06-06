from __future__ import annotations

from datetime import date, datetime, time, timedelta

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import (
    QAbstractItemView,
    QCheckBox,
    QComboBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QScrollArea,
    QTabWidget,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from core.scheduler import (
    DEFAULT_GRANULARITY_MINUTES,
    allocate_tasks_to_free_blocks,
    attach_daily_targets_to_tasks,
    build_busy_blocks,
    build_capacity_summary,
    build_free_blocks,
)
from data.db import (
    delete_a_task,
    delete_event,
    delete_routine_event,
    get_setting,
    insert_a_task,
    insert_a_task_candidate,
    insert_event,
    insert_routine_event,
    has_daily_log,
    list_a_tasks,
    list_a_task_candidates,
    list_events_by_date,
    list_expired_active_a_tasks,
    list_routine_events_for_date,
    mark_a_task_candidate_converted,
    recompute_remaining_minutes,
    set_setting,
    update_a_task_total_minutes,
    update_a_task_status,
    upsert_daily_log,
)


EVERYDAY_WEEKDAYS = "0,1,2,3,4,5,6"
WEEKDAY_LABELS = ["月", "火", "水", "木", "金", "土", "日"]
MORNING_CHECK_TIME_KEY = "morning_check_time"
NIGHT_LOG_TIME_KEY = "night_log_time"
DEFAULT_MORNING_CHECK_TIME = "08:00"
DEFAULT_NIGHT_LOG_TIME = "23:00"
TASK_SCALE_LABELS = {
    "weekly": "週単位",
    "monthly": "月単位",
    "yearly": "年単位",
    "other": "その他",
}


class DayView(QWidget):
    def __init__(self, target_date: str | None = None) -> None:
        super().__init__()
        self.target_date = target_date or date.today().isoformat()
        self.reminder_targets: list[dict[str, str]] = []
        self.notified_reminder_keys: set[str] = set()
        self.notified_check_reminder_keys: set[str] = set()
        self.displayed_event_refs: list[tuple[str, int]] = []
        self.displayed_missing_log_refs: list[tuple[str, int]] = []
        self.displayed_expired_task_ids: list[int] = []
        self.displayed_duration_only_routine_ids: list[int] = []
        self.displayed_candidate_ids: list[int] = []
        self.copied_candidate_id: int | None = None

        self.date_label = QLabel()
        self.target_date_input = QLineEdit(self.target_date)
        self.change_date_button = QPushButton("日付変更")
        self.refresh_button = QPushButton("再計算")
        self.status_label = QLabel()
        self.status_label.setWordWrap(True)
        self.candidate_title_input = QLineEdit()
        self.candidate_memo_input = QLineEdit()
        self.candidate_category_input = QLineEdit()
        self.add_candidate_button = QPushButton("候補メモ追加")
        self.copy_candidate_to_task_button = QPushButton("選択候補をA追加フォームへコピー")
        self.task_title_input = QLineEdit()
        self.task_start_input = QLineEdit()
        self.task_deadline_input = QLineEdit()
        self.task_minutes_input = QLineEdit()
        self.task_scale_label_input = QComboBox()
        self.add_task_button = QPushButton("Aタスク追加")
        self.task_total_update_input = QLineEdit()
        self.update_task_total_button = QPushButton("A想定時間更新")
        self.event_title_input = QLineEdit()
        self.event_start_input = QLineEdit()
        self.event_end_input = QLineEdit()
        self.event_remind_start_input = QCheckBox()
        self.event_remind_end_input = QCheckBox()
        self.event_note_input = QLineEdit()
        self.add_event_button = QPushButton("B予定追加")
        self.routine_mode_input = QComboBox()
        self.routine_title_input = QLineEdit()
        self.routine_start_input = QLineEdit()
        self.routine_end_input = QLineEdit()
        self.routine_duration_input = QLineEdit()
        self.routine_everyday_input = QCheckBox("毎日繰り返す")
        self.routine_weekly_input = QCheckBox("毎週繰り返す")
        self.routine_repeat_hint_label = QLabel()
        self.routine_everyday_hint_label = QLabel("毎日このCルールを適用")
        self.routine_weekly_hint_label = QLabel("選択した曜日に毎週適用")
        self.routine_weekday_inputs = [
            QCheckBox(weekday_label) for weekday_label in WEEKDAY_LABELS
        ]
        self.routine_remind_start_input = QCheckBox()
        self.routine_remind_end_input = QCheckBox()
        self.routine_note_input = QLineEdit()
        self.add_routine_button = QPushButton("Cルール追加")
        self.log_task_input = QComboBox()
        self.log_date_input = QLineEdit(self.target_date)
        self.log_minutes_input = QLineEdit()
        self.log_reflection_input = QLineEdit()
        self.save_log_button = QPushButton("日次ログ保存")
        self.delete_task_button = QPushButton("選択Aタスク削除")
        self.delete_event_button = QPushButton("選択B/C予定削除")
        self.delete_duration_only_button = QPushButton("選択時間未指定C削除")
        self.record_zero_missing_log_button = QPushButton("0分として記録")
        self.mark_expired_task_completed_button = QPushButton("完了にする")
        self.mark_expired_task_incomplete_button = QPushButton("未完了にする")
        self.granularity_label = QLabel(f"計算粒度: {DEFAULT_GRANULARITY_MINUTES}分")
        self.reminder_summary_label = QLabel()
        self.reminder_summary_label.setWordWrap(True)
        self.reminder_summary_label.setText("現在のリマインド対象: 0件")
        self.morning_check_time_input = QLineEdit()
        self.night_log_time_input = QLineEdit()
        self.save_check_times_button = QPushButton("確認時刻を保存")
        self.capacity_summary_label = QLabel()
        self.capacity_summary_label.setWordWrap(True)
        self.expired_tasks_summary_label = QLabel()
        self.expired_tasks_summary_label.setWordWrap(True)
        self.missing_logs_summary_label = QLabel()
        self.missing_logs_summary_label.setWordWrap(True)
        self.duration_only_summary_label = QLabel()
        self.schedule_start_input = QLineEdit(self.target_date)
        self.schedule_period_input = QComboBox()
        self.update_schedule_button = QPushButton("更新")
        self.schedule_overview_summary_label = QLabel(
            "duration_only Cは時刻がないため予定一覧対象外です。"
        )
        self.schedule_overview_summary_label.setWordWrap(True)

        self.events_table = self._create_table(["ID", "種別", "タイトル", "開始", "終了", "メモ"])
        self.schedule_overview_table = self._create_table(
            ["日付", "開始", "終了", "種別", "タイトル", "繰り返し種別", "メモ"]
        )
        self.expired_tasks_table = self._create_table(
            ["タスク名", "締切", "総時間", "残り時間", "進捗"]
        )
        self.missing_logs_table = self._create_table(["日付", "Aタスク名", "予定分数"])
        self.duration_only_table = self._create_table(["ID", "タイトル", "所要時間(分)", "メモ"])
        self.candidates_table = self._create_table(
            ["ID", "タイトル", "カテゴリ", "メモ", "A化済み", "作成日"]
        )
        self.tasks_table = self._create_table(
            [
                "ID",
                "タイトル",
                "タスク分類",
                "開始",
                "締切",
                "総時間(分)",
                "残り(分)",
                "進捗",
                "進捗バー",
                "今日の推奨(分)",
                "備考",
            ]
        )
        self.allocations_table = self._create_table(
            ["開始", "終了", "タスク名", "分数"]
        )
        self.candidates_table.setColumnHidden(0, True)
        self.tasks_table.setColumnHidden(0, True)
        self._set_table_minimum_heights()
        self._load_check_reminder_settings()
        self._sync_target_date_inputs()

        self._build_layout()
        self.change_date_button.clicked.connect(self.refresh)
        self.refresh_button.clicked.connect(self.refresh)
        self.add_candidate_button.clicked.connect(self.add_a_task_candidate)
        self.copy_candidate_to_task_button.clicked.connect(
            self.copy_selected_candidate_to_task_form
        )
        self.add_task_button.clicked.connect(self.add_a_task)
        self.update_task_total_button.clicked.connect(self.update_selected_task_total)
        self.add_event_button.clicked.connect(self.add_b_event)
        self.add_routine_button.clicked.connect(self.add_routine_event)
        self.update_schedule_button.clicked.connect(self.refresh_schedule_overview)
        self.routine_mode_input.currentTextChanged.connect(self._update_routine_mode_inputs)
        self.routine_everyday_input.toggled.connect(self._on_routine_everyday_toggled)
        self.routine_weekly_input.toggled.connect(self._on_routine_weekly_toggled)
        for weekday_input in self.routine_weekday_inputs:
            weekday_input.toggled.connect(
                lambda _checked=False: self._update_routine_repeat_hint()
            )
        self.save_log_button.clicked.connect(self.save_daily_log)
        self.delete_task_button.clicked.connect(self.delete_selected_task)
        self.delete_event_button.clicked.connect(self.delete_selected_event)
        self.delete_duration_only_button.clicked.connect(
            self.delete_selected_duration_only_routine
        )
        self.record_zero_missing_log_button.clicked.connect(
            self.record_selected_missing_log_as_zero
        )
        self.mark_expired_task_completed_button.clicked.connect(
            self.mark_selected_expired_task_completed
        )
        self.mark_expired_task_incomplete_button.clicked.connect(
            self.mark_selected_expired_task_incomplete
        )
        self.save_check_times_button.clicked.connect(self.save_check_reminder_settings)
        self._update_routine_mode_inputs()
        self._update_routine_repeat_hint()
        self.refresh()
        self.reminder_timer = QTimer(self)
        self.reminder_timer.setInterval(60_000)
        self.reminder_timer.timeout.connect(self.check_reminders)
        self.reminder_timer.start()

    def _build_layout(self) -> None:
        root = QVBoxLayout(self)

        tabs = QTabWidget()
        tabs.addTab(self._build_today_tab(), "今日の確認")
        tabs.addTab(self._build_schedule_tab(), "予定確認")
        tabs.addTab(self._build_edit_tab(), "入力・編集")
        tabs.addTab(self._build_settings_tab(), "設定")
        root.addWidget(tabs)
        root.addWidget(self._wrap_message())

    def _build_today_tab(self) -> QWidget:
        return self._build_scroll_tab(
            [
                self._build_date_controls(),
                self._wrap_capacity_summary(),
                self._wrap_missing_logs(),
                self._wrap_expired_tasks(),
                self._wrap_table(
                    "今日のAタスク",
                    self.tasks_table,
                    self.delete_task_button,
                ),
                self._wrap_table("今日のA割当結果", self.allocations_table),
                self._wrap_table(
                    "今日のB予定・fixed_time C",
                    self.events_table,
                    self.delete_event_button,
                ),
                self._wrap_duration_only_table(),
            ]
        )

    def _build_edit_tab(self) -> QWidget:
        return self._build_scroll_tab(
            [
                self._build_add_candidate_form(),
                self._wrap_table(
                    "Aタスク候補メモ一覧",
                    self.candidates_table,
                    self.copy_candidate_to_task_button,
                ),
                self._build_add_task_form(),
                self._build_update_task_total_form(),
                self._build_add_event_form(),
                self._build_add_routine_form(),
                self._build_daily_log_form(),
            ]
        )

    def _build_schedule_tab(self) -> QWidget:
        return self._build_scroll_tab(
            [
                self._build_schedule_controls(),
                self._wrap_schedule_overview_table(),
            ]
        )

    def _build_settings_tab(self) -> QWidget:
        return self._build_scroll_tab(
            [
                self._wrap_reminder_settings(),
            ]
        )

    def _build_scroll_tab(self, widgets: list[QWidget]) -> QWidget:
        tab = QWidget()
        tab_layout = QVBoxLayout(tab)

        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        tab_layout.addWidget(scroll_area)

        content = QWidget()
        scroll_area.setWidget(content)
        content_layout = QVBoxLayout(content)

        for widget in widgets:
            content_layout.addWidget(widget)
        content_layout.addStretch(1)
        return tab

    def refresh(self) -> None:
        error = self._apply_target_date_from_input()
        if error:
            self.status_label.setText(error)
            return

        self.date_label.setText(f"日付: {self.target_date}")

        try:
            events = [
                dict(event, source="event")
                for event in list_events_by_date(self.target_date)
                if event["type"] == "B"
            ]
            routine_events = list_routine_events_for_date(self.target_date)
            fixed_time_routines = [
                event for event in routine_events
                if event.get("mode") == "fixed_time"
            ]
            duration_only_routines = [
                event for event in routine_events
                if event.get("mode") == "duration_only"
            ]
            scheduled_events = sorted(
                events + fixed_time_routines,
                key=lambda event: (str(event.get("start_dt", "")), _event_display_id(event)),
            )
            busy_blocks = build_busy_blocks(scheduled_events)
            free_blocks = build_free_blocks(self.target_date, busy_blocks)
            active_tasks = list_a_tasks()
            candidates = list_a_task_candidates()
            expired_tasks = list_expired_active_a_tasks(self.target_date)
            tasks = _tasks_available_on_date(active_tasks, self.target_date)
            tasks_with_targets = attach_daily_targets_to_tasks(tasks, today=self.target_date)
            allocations = allocate_tasks_to_free_blocks(
                tasks=tasks,
                free_blocks=free_blocks,
                today=self.target_date,
            )
            capacity_summary = build_capacity_summary(
                free_blocks=free_blocks,
                duration_only_events=duration_only_routines,
                tasks_with_targets=tasks_with_targets,
                allocations=allocations,
                today=self.target_date,
            )
            missing_logs = self._build_missing_logs_for_previous_day(active_tasks)
        except Exception as exc:
            self._clear_tables()
            self.status_label.setText(f"読み込みに失敗しました: {exc}")
            return

        self._set_events(scheduled_events)
        self._set_missing_logs(missing_logs)
        self._set_expired_tasks(expired_tasks)
        self._set_capacity_summary(capacity_summary)
        self._set_duration_only_routines(
            duration_only_routines,
            int(capacity_summary["floating_c_minutes"]),
        )
        self._set_candidates(candidates)
        self._set_tasks(tasks_with_targets)
        self._set_allocations(allocations)
        self._set_log_task_options(tasks)
        self._set_reminder_targets(scheduled_events, allocations)
        self.refresh_schedule_overview(set_status=False)
        capacity_status = " / 過密警告" if capacity_summary["is_over_capacity"] else ""
        self.status_label.setText(
            f"B/C予定 {len(scheduled_events)}件 / 時間未指定C 合計 "
            f"{capacity_summary['floating_c_minutes']}分 / Aタスク {len(tasks)}件 / "
            f"候補 {len(candidates)}件 / "
            f"割当 {len(allocations)}件 / 未入力ログ {len(missing_logs)}件 / "
            f"期限切れA {len(expired_tasks)}件{capacity_status}"
        )

    def _apply_target_date_from_input(self) -> str | None:
        target_date = self.target_date_input.text().strip()
        if not target_date:
            return "対象日付を入力してください。"

        try:
            date.fromisoformat(target_date)
        except ValueError:
            return "対象日付はYYYY-MM-DD形式で入力してください。"

        if target_date != self.target_date:
            old_target_date = self.target_date
            self.target_date = target_date
            self._sync_target_date_inputs(old_target_date)

        return None

    def refresh_schedule_overview(
        self,
        checked: bool = False,
        *,
        set_status: bool = True,
    ) -> None:
        del checked
        start_text = self.schedule_start_input.text().strip()
        if not start_text:
            self._set_schedule_overview_error("予定確認の開始日を入力してください。")
            if set_status:
                self.status_label.setText("予定確認の開始日を入力してください。")
            return

        try:
            start_date = date.fromisoformat(start_text)
        except ValueError:
            self._set_schedule_overview_error("開始日はYYYY-MM-DD形式で入力してください。")
            if set_status:
                self.status_label.setText("開始日はYYYY-MM-DD形式で入力してください。")
            return

        period_days = int(self.schedule_period_input.currentData() or 7)
        if period_days not in (7, 14, 30):
            period_days = 7

        try:
            entries = self._build_schedule_overview_entries(start_date, period_days)
        except Exception as exc:
            message = f"予定一覧の読み込みに失敗しました: {exc}"
            self._set_schedule_overview_error(message)
            if set_status:
                self.status_label.setText(message)
            return

        self._set_schedule_overview(entries, start_text, period_days)
        if set_status:
            self.status_label.setText(
                f"予定一覧を更新しました: {start_text}から{period_days}日分 / {len(entries)}件"
            )

    def add_a_task_candidate(self) -> None:
        title = self.candidate_title_input.text().strip()
        memo = self.candidate_memo_input.text().strip()
        category = self.candidate_category_input.text().strip()

        error = self._validate_candidate_input(title)
        if error:
            self.status_label.setText(error)
            return

        try:
            insert_a_task_candidate(
                title=title,
                memo=memo,
                category=category,
            )
        except Exception as exc:
            self.status_label.setText(f"Aタスク候補メモの保存に失敗しました: {exc}")
            return

        self._clear_candidate_inputs()
        self.refresh()
        self.status_label.setText("Aタスク候補メモを追加しました。")

    def copy_selected_candidate_to_task_form(self) -> None:
        candidate_id = self._selected_candidate_id()
        if candidate_id is None:
            self.status_label.setText("A追加フォームへコピーする候補を選択してください。")
            return

        row = self.candidates_table.currentRow()
        title_item = self.candidates_table.item(row, 1)
        title = title_item.text().strip() if title_item is not None else ""
        if not title:
            self.status_label.setText("候補タイトルを読み取れませんでした。")
            return

        self.task_title_input.setText(title)
        self.task_start_input.setText(self.target_date)
        other_index = self.task_scale_label_input.findData("other")
        if other_index >= 0:
            self.task_scale_label_input.setCurrentIndex(other_index)
        self.copied_candidate_id = candidate_id
        self.status_label.setText(
            "候補タイトルをAタスク追加フォームへコピーしました。締切日と必要時間を入力してください。"
        )

    def add_a_task(self) -> None:
        title = self.task_title_input.text().strip()
        start_date = self.task_start_input.text().strip()
        deadline_date = self.task_deadline_input.text().strip()
        total_minutes_text = self.task_minutes_input.text().strip()
        task_scale_label = str(self.task_scale_label_input.currentData())

        error = self._validate_a_task_input(
            title,
            start_date,
            deadline_date,
            total_minutes_text,
        )
        if error:
            self.status_label.setText(error)
            return

        try:
            total_minutes = int(total_minutes_text)
            insert_a_task(
                title=title,
                start_date=start_date,
                deadline_date=deadline_date,
                total_minutes=total_minutes,
                task_scale_label=task_scale_label,
            )
        except Exception as exc:
            self.status_label.setText(f"Aタスクの保存に失敗しました: {exc}")
            return

        status_message = "Aタスクを追加しました。"
        if self.copied_candidate_id is not None:
            try:
                mark_a_task_candidate_converted(self.copied_candidate_id)
                status_message = "Aタスクを追加し、候補メモをA化済みにしました。"
            except Exception as exc:
                status_message = f"Aタスクを追加しましたが、候補メモの更新に失敗しました: {exc}"

        self.copied_candidate_id = None
        self.task_title_input.clear()
        self.task_start_input.setText(self.target_date)
        self.task_deadline_input.setText(self.target_date)
        self.task_minutes_input.clear()
        self.task_scale_label_input.setCurrentIndex(
            max(self.task_scale_label_input.findData("other"), 0)
        )
        self.refresh()
        self.status_label.setText(status_message)

    def update_selected_task_total(self) -> None:
        a_task_id = self._selected_row_id(self.tasks_table)
        new_total_minutes_text = self.task_total_update_input.text().strip()

        error = self._validate_task_total_update_input(
            a_task_id,
            new_total_minutes_text,
        )
        if error:
            self.status_label.setText(error)
            return

        try:
            new_total_minutes = int(new_total_minutes_text)
            remaining_minutes = update_a_task_total_minutes(
                a_task_id=int(a_task_id),
                new_total_minutes=new_total_minutes,
            )
        except Exception as exc:
            self.status_label.setText(f"A想定時間の更新に失敗しました: {exc}")
            return

        self.task_total_update_input.clear()
        self.refresh()
        self.status_label.setText(
            f"A想定時間を更新しました。残り時間: {remaining_minutes}分"
        )

    def add_b_event(self) -> None:
        title = self.event_title_input.text().strip()
        start_dt = self.event_start_input.text().strip()
        end_dt = self.event_end_input.text().strip()
        note = self.event_note_input.text().strip()

        error = self._validate_b_event_input(title, start_dt, end_dt, note)
        if error:
            self.status_label.setText(error)
            return

        try:
            insert_event(
                event_type="B",
                title=title,
                start_dt=start_dt,
                end_dt=end_dt,
                remind_start=int(self.event_remind_start_input.isChecked()),
                remind_end=int(self.event_remind_end_input.isChecked()),
                note=note,
            )
        except Exception as exc:
            self.status_label.setText(f"B予定の保存に失敗しました: {exc}")
            return

        self._clear_event_inputs()
        self.refresh()
        self.status_label.setText("B予定を追加しました。")

    def add_routine_event(self) -> None:
        mode = self.routine_mode_input.currentText().strip()
        title = self.routine_title_input.text().strip()
        start_time = self.routine_start_input.text().strip()
        end_time = self.routine_end_input.text().strip()
        duration_minutes_text = self.routine_duration_input.text().strip()
        note = self.routine_note_input.text().strip()

        error = self._validate_routine_event_input(
            title=title,
            mode=mode,
            start_time=start_time,
            end_time=end_time,
            duration_minutes_text=duration_minutes_text,
        )
        if error:
            self.status_label.setText(error)
            return

        repeat_error = self._validate_routine_repeat_setting()
        if repeat_error:
            self.status_label.setText(repeat_error)
            return

        duration_minutes = (
            int(duration_minutes_text)
            if mode == "duration_only"
            else None
        )
        weekdays = self._routine_weekdays_from_repeat_setting()

        try:
            insert_routine_event(
                title=title,
                mode=mode,
                start_time=start_time if mode == "fixed_time" else None,
                end_time=end_time if mode == "fixed_time" else None,
                duration_minutes=duration_minutes,
                weekdays=weekdays,
                remind_start=int(self.routine_remind_start_input.isChecked()),
                remind_end=int(self.routine_remind_end_input.isChecked()),
                note=note,
            )
        except Exception as exc:
            self.status_label.setText(f"Cルールの保存に失敗しました: {exc}")
            return

        self._clear_routine_inputs()
        self.refresh()
        self.status_label.setText("Cルールを追加しました。")

    def save_daily_log(self) -> None:
        a_task_id = self.log_task_input.currentData()
        log_date = self.log_date_input.text().strip()
        actual_minutes_text = self.log_minutes_input.text().strip()
        reflection = self.log_reflection_input.text().strip()

        error = self._validate_daily_log_input(
            a_task_id,
            log_date,
            actual_minutes_text,
            reflection,
        )
        if error:
            self.status_label.setText(error)
            return

        try:
            actual_minutes = int(actual_minutes_text)
            upsert_daily_log(
                log_date=log_date,
                a_task_id=int(a_task_id),
                actual_minutes=actual_minutes,
                reflection=reflection,
            )
            recompute_remaining_minutes(int(a_task_id))
        except Exception as exc:
            self.status_label.setText(f"日次ログの保存に失敗しました: {exc}")
            return

        self._clear_daily_log_inputs()
        self.refresh()
        self.status_label.setText("日次ログを保存しました。")

    def record_selected_missing_log_as_zero(self) -> None:
        missing_log_ref = self._selected_missing_log_ref()
        if missing_log_ref is None:
            self.status_label.setText("0分として記録する未入力ログを選択してください。")
            return

        log_date, a_task_id = missing_log_ref
        try:
            upsert_daily_log(
                log_date=log_date,
                a_task_id=a_task_id,
                actual_minutes=0,
                reflection="未実施",
            )
            recompute_remaining_minutes(a_task_id)
        except Exception as exc:
            self.status_label.setText(f"0分ログの保存に失敗しました: {exc}")
            return

        self.refresh()
        self.status_label.setText("0分ログを記録しました。")

    def mark_selected_expired_task_completed(self) -> None:
        self._update_selected_expired_task_status("completed", "完了")

    def mark_selected_expired_task_incomplete(self) -> None:
        self._update_selected_expired_task_status("incomplete", "未完了")

    def _update_selected_expired_task_status(self, status: str, label: str) -> None:
        a_task_id = self._selected_expired_task_id()
        if a_task_id is None:
            self.status_label.setText("期限切れAタスクを選択してください。")
            return

        try:
            update_a_task_status(a_task_id, status)
        except Exception as exc:
            self.status_label.setText(f"期限切れAタスクの更新に失敗しました: {exc}")
            return

        self.refresh()
        self.status_label.setText(f"期限切れAタスクを{label}にしました。")

    def delete_selected_task(self) -> None:
        a_task_id = self._selected_row_id(self.tasks_table)
        if a_task_id is None:
            self.status_label.setText("削除するAタスクを選択してください。")
            return

        if not self._confirm_delete("選択したAタスク"):
            return

        try:
            delete_a_task(a_task_id)
        except Exception as exc:
            self.status_label.setText(f"Aタスクの削除に失敗しました: {exc}")
            return

        self.refresh()
        self.status_label.setText("Aタスクを削除しました。")

    def delete_selected_event(self) -> None:
        event_ref = self._selected_event_ref()
        if event_ref is None:
            self.status_label.setText("削除するB/C予定を選択してください。")
            return

        source, item_id = event_ref
        target = "選択したCルール" if source == "routine" else "選択したB予定"
        if not self._confirm_delete(target):
            return

        try:
            if source == "routine":
                delete_routine_event(item_id)
            else:
                delete_event(item_id)
        except Exception as exc:
            self.status_label.setText(f"B/C予定の削除に失敗しました: {exc}")
            return

        self.refresh()
        self.status_label.setText("B/C予定を削除しました。")

    def delete_selected_duration_only_routine(self) -> None:
        routine_id = self._selected_duration_only_routine_id()
        if routine_id is None:
            self.status_label.setText("削除する時間未指定Cを選択してください。")
            return

        if not self._confirm_delete("選択した時間未指定C"):
            return

        try:
            delete_routine_event(routine_id)
        except Exception as exc:
            self.status_label.setText(f"時間未指定Cの削除に失敗しました: {exc}")
            return

        self.refresh()
        self.status_label.setText("時間未指定Cを削除しました。")

    def check_reminders(self) -> None:
        now = datetime.now()
        current_date = now.date().isoformat()
        current_time = now.strftime("%H:%M")
        current_minute = now.strftime("%Y-%m-%dT%H:%M")
        messages = []

        check_reminders = [
            (
                "morning",
                self.morning_check_time,
                "今日の予定を確認してください",
            ),
            (
                "night",
                self.night_log_time,
                "今日のAログを入力してください",
            ),
        ]
        for reminder_type, reminder_time, message in check_reminders:
            if current_time != reminder_time:
                continue

            key = f"{current_date}:{reminder_type}"
            if key in self.notified_check_reminder_keys:
                continue

            self.notified_check_reminder_keys.add(key)
            messages.append(message)

        for target in self.reminder_targets:
            if target["start_minute"] != current_minute:
                continue
            if target["key"] in self.notified_reminder_keys:
                continue

            self.notified_reminder_keys.add(target["key"])
            messages.append(target["message"])

        if messages:
            self.status_label.setText("リマインド: " + " / ".join(messages))

    def save_check_reminder_settings(self) -> None:
        morning_time = _normalize_hhmm(self.morning_check_time_input.text())
        night_time = _normalize_hhmm(self.night_log_time_input.text())

        if morning_time is None:
            self.status_label.setText("朝の予定確認時刻はHH:MM形式で入力してください。")
            return
        if night_time is None:
            self.status_label.setText("夜のログ入力確認時刻はHH:MM形式で入力してください。")
            return

        try:
            set_setting(MORNING_CHECK_TIME_KEY, morning_time)
            set_setting(NIGHT_LOG_TIME_KEY, night_time)
        except Exception as exc:
            self.status_label.setText(f"確認時刻の保存に失敗しました: {exc}")
            return

        self.morning_check_time = morning_time
        self.night_log_time = night_time
        self.morning_check_time_input.setText(morning_time)
        self.night_log_time_input.setText(night_time)
        self._update_reminder_summary()
        self.status_label.setText("確認時刻を保存しました。")

    def _build_date_controls(self) -> QGroupBox:
        group = QGroupBox("日付操作")
        layout = QHBoxLayout(group)
        layout.addWidget(self.date_label)
        layout.addStretch(1)
        layout.addWidget(QLabel("対象日付"))
        layout.addWidget(self.target_date_input)
        layout.addWidget(self.change_date_button)
        layout.addWidget(self.refresh_button)
        return group

    def _build_schedule_controls(self) -> QGroupBox:
        group = QGroupBox("表示条件")
        layout = QHBoxLayout(group)

        self.schedule_start_input.setPlaceholderText("YYYY-MM-DD")
        if self.schedule_period_input.count() == 0:
            self.schedule_period_input.addItem("7日", 7)
            self.schedule_period_input.addItem("14日", 14)
            self.schedule_period_input.addItem("30日", 30)

        layout.addWidget(QLabel("開始日"))
        layout.addWidget(self.schedule_start_input)
        layout.addWidget(QLabel("表示期間"))
        layout.addWidget(self.schedule_period_input)
        layout.addWidget(self.update_schedule_button)
        layout.addStretch(1)
        return group

    def _wrap_schedule_overview_table(self) -> QGroupBox:
        group = QGroupBox("予定一覧")
        layout = QVBoxLayout(group)
        layout.addWidget(self.schedule_overview_summary_label)
        layout.addWidget(self.schedule_overview_table)
        return group

    def _build_add_candidate_form(self) -> QGroupBox:
        group = QGroupBox("Aタスク候補メモ追加")
        form = QFormLayout(group)

        self.candidate_title_input.setPlaceholderText("例: 論文整理をAタスク化するか検討")
        self.candidate_memo_input.setPlaceholderText("例: 週末に必要時間を見積もる")
        self.candidate_category_input.setPlaceholderText("例: 研究")

        form.addRow("タイトル", self.candidate_title_input)
        form.addRow("メモ", self.candidate_memo_input)
        form.addRow("想定カテゴリ", self.candidate_category_input)
        form.addRow(self.add_candidate_button)
        return group

    def _build_add_task_form(self) -> QGroupBox:
        group = QGroupBox("Aタスク追加")
        form = QFormLayout(group)

        self.task_title_input.setPlaceholderText("例: レポート作成")
        self.task_start_input.setPlaceholderText("YYYY-MM-DD")
        self.task_deadline_input.setPlaceholderText("YYYY-MM-DD")
        self.task_minutes_input.setPlaceholderText("例: 120")
        if self.task_scale_label_input.count() == 0:
            self.task_scale_label_input.addItem("週単位タスク", "weekly")
            self.task_scale_label_input.addItem("月単位タスク", "monthly")
            self.task_scale_label_input.addItem("年単位タスク", "yearly")
            self.task_scale_label_input.addItem("その他", "other")
            self.task_scale_label_input.setCurrentIndex(
                self.task_scale_label_input.findData("other")
            )

        form.addRow("タイトル", self.task_title_input)
        form.addRow("タスク分類", self.task_scale_label_input)
        form.addRow("開始日 YYYY-MM-DD", self.task_start_input)
        form.addRow("締切日", self.task_deadline_input)
        form.addRow("必要時間(分)", self.task_minutes_input)
        form.addRow(self.add_task_button)
        return group

    def _build_update_task_total_form(self) -> QGroupBox:
        group = QGroupBox("A想定時間更新")
        form = QFormLayout(group)

        self.task_total_update_input.setPlaceholderText("例: 1800")

        form.addRow("新しい想定総時間(分)", self.task_total_update_input)
        form.addRow(self.update_task_total_button)
        return group

    def _build_add_event_form(self) -> QGroupBox:
        group = QGroupBox("B予定追加")
        form = QFormLayout(group)

        self.event_title_input.setPlaceholderText("例: ゼミ")
        self.event_start_input.setPlaceholderText("YYYY-MM-DDTHH:MM:SS")
        self.event_end_input.setPlaceholderText("YYYY-MM-DDTHH:MM:SS")
        self.event_note_input.setPlaceholderText("例: 研究室")

        form.addRow("タイトル", self.event_title_input)
        form.addRow("開始日時", self.event_start_input)
        form.addRow("終了日時", self.event_end_input)
        form.addRow("開始リマインド", self.event_remind_start_input)
        form.addRow("終了リマインド", self.event_remind_end_input)
        form.addRow("メモ", self.event_note_input)
        form.addRow(self.add_event_button)
        return group

    def _build_add_routine_form(self) -> QGroupBox:
        group = QGroupBox("Cルール追加")
        form = QFormLayout(group)

        self.routine_mode_input.addItems(["fixed_time", "duration_only"])
        self.routine_title_input.setPlaceholderText("例: 睡眠")
        self.routine_start_input.setPlaceholderText("HH:MM")
        self.routine_end_input.setPlaceholderText("HH:MM")
        self.routine_duration_input.setPlaceholderText("例: 45")
        self.routine_note_input.setPlaceholderText("例: 毎日")
        self.routine_everyday_input.setChecked(True)
        self.routine_weekly_input.setChecked(False)
        self._clear_routine_weekday_inputs()
        self._set_routine_weekday_inputs_enabled(False)
        self.routine_repeat_hint_label.setWordWrap(True)
        self.routine_everyday_hint_label.setWordWrap(True)
        self.routine_weekly_hint_label.setWordWrap(True)

        repeat_widget = QWidget()
        repeat_layout = QVBoxLayout(repeat_widget)
        repeat_layout.setContentsMargins(0, 0, 0, 0)

        everyday_row = QWidget()
        everyday_layout = QHBoxLayout(everyday_row)
        everyday_layout.setContentsMargins(0, 0, 0, 0)
        everyday_layout.addWidget(self.routine_everyday_input)
        everyday_layout.addWidget(self.routine_everyday_hint_label)
        everyday_layout.addStretch(1)

        weekly_row = QWidget()
        weekly_layout = QHBoxLayout(weekly_row)
        weekly_layout.setContentsMargins(0, 0, 0, 0)
        weekly_layout.addWidget(self.routine_weekly_input)
        weekly_layout.addWidget(self.routine_weekly_hint_label)
        weekly_layout.addStretch(1)

        weekday_row = QWidget()
        weekday_layout = QHBoxLayout(weekday_row)
        weekday_layout.setContentsMargins(16, 0, 0, 0)
        for weekday_input in self.routine_weekday_inputs:
            weekday_layout.addWidget(weekday_input)
        weekday_layout.addStretch(1)

        repeat_layout.addWidget(everyday_row)
        repeat_layout.addWidget(weekly_row)
        repeat_layout.addWidget(weekday_row)
        repeat_layout.addWidget(self.routine_repeat_hint_label)

        form.addRow("mode", self.routine_mode_input)
        form.addRow("タイトル", self.routine_title_input)
        form.addRow("開始時刻", self.routine_start_input)
        form.addRow("終了時刻", self.routine_end_input)
        form.addRow("所要時間(分)", self.routine_duration_input)
        form.addRow("繰り返し", repeat_widget)
        form.addRow("開始リマインド", self.routine_remind_start_input)
        form.addRow("終了リマインド", self.routine_remind_end_input)
        form.addRow("メモ", self.routine_note_input)
        form.addRow(self.add_routine_button)
        return group

    def _build_daily_log_form(self) -> QGroupBox:
        group = QGroupBox("日次ログ入力")
        form = QFormLayout(group)

        self.log_date_input.setPlaceholderText("YYYY-MM-DD")
        self.log_minutes_input.setPlaceholderText("例: 45")
        self.log_reflection_input.setPlaceholderText("例: 集中できた")

        form.addRow("Aタスク", self.log_task_input)
        form.addRow("ログ日付", self.log_date_input)
        form.addRow("実績時間(分)", self.log_minutes_input)
        form.addRow("反省", self.log_reflection_input)
        form.addRow(self.save_log_button)
        return group

    def _create_table(self, headers: list[str]) -> QTableWidget:
        table = QTableWidget(0, len(headers))
        table.setHorizontalHeaderLabels(headers)
        table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        table.verticalHeader().setVisible(False)
        table.setAlternatingRowColors(True)
        table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        table.setSelectionBehavior(QAbstractItemView.SelectRows)
        return table

    def _set_table_minimum_heights(self) -> None:
        self.events_table.setMinimumHeight(150)
        self.schedule_overview_table.setMinimumHeight(360)
        self.expired_tasks_table.setMinimumHeight(90)
        self.expired_tasks_table.setMaximumHeight(110)
        self.missing_logs_table.setMinimumHeight(90)
        self.missing_logs_table.setMaximumHeight(110)
        self.duration_only_table.setMinimumHeight(120)
        self.candidates_table.setMinimumHeight(150)
        self.tasks_table.setMinimumHeight(190)
        self.allocations_table.setMinimumHeight(120)
        self.allocations_table.setMaximumHeight(150)

    def _wrap_table(
        self,
        title: str,
        table: QTableWidget,
        action_button: QPushButton | None = None,
    ) -> QGroupBox:
        group = QGroupBox(title)
        layout = QVBoxLayout(group)
        layout.addWidget(table)
        if action_button is not None:
            actions = QHBoxLayout()
            actions.addStretch(1)
            actions.addWidget(action_button)
            layout.addLayout(actions)
        return group

    def _wrap_capacity_summary(self) -> QGroupBox:
        group = QGroupBox("今日の状態サマリー")
        layout = QVBoxLayout(group)
        layout.addWidget(self.granularity_label)
        layout.addWidget(self.capacity_summary_label)
        return group

    def _wrap_expired_tasks(self) -> QGroupBox:
        group = QGroupBox("期限切れAタスク")
        layout = QVBoxLayout(group)
        layout.addWidget(self.expired_tasks_summary_label)
        layout.addWidget(self.expired_tasks_table)
        actions = QHBoxLayout()
        actions.addStretch(1)
        actions.addWidget(self.mark_expired_task_completed_button)
        actions.addWidget(self.mark_expired_task_incomplete_button)
        layout.addLayout(actions)
        return group

    def _wrap_missing_logs(self) -> QGroupBox:
        group = QGroupBox("前日の未入力ログ")
        layout = QVBoxLayout(group)
        layout.addWidget(self.missing_logs_summary_label)
        layout.addWidget(self.missing_logs_table)
        actions = QHBoxLayout()
        actions.addStretch(1)
        actions.addWidget(self.record_zero_missing_log_button)
        layout.addLayout(actions)
        return group

    def _wrap_duration_only_table(self) -> QGroupBox:
        group = QGroupBox("時間未指定C")
        layout = QVBoxLayout(group)
        layout.addWidget(self.duration_only_summary_label)
        layout.addWidget(self.duration_only_table)
        actions = QHBoxLayout()
        actions.addStretch(1)
        actions.addWidget(self.delete_duration_only_button)
        layout.addLayout(actions)
        return group

    def _wrap_reminder_settings(self) -> QGroupBox:
        group = QGroupBox("アプリ内リマインド")
        layout = QVBoxLayout(group)
        form = QFormLayout()

        self.morning_check_time_input.setPlaceholderText("08:00")
        self.night_log_time_input.setPlaceholderText("23:00")

        form.addRow("朝の予定確認時刻", self.morning_check_time_input)
        form.addRow("夜のログ入力確認時刻", self.night_log_time_input)

        layout.addWidget(self.reminder_summary_label)
        layout.addLayout(form)
        actions = QHBoxLayout()
        actions.addStretch(1)
        actions.addWidget(self.save_check_times_button)
        layout.addLayout(actions)
        return group

    def _wrap_message(self) -> QGroupBox:
        group = QGroupBox("メッセージ")
        layout = QVBoxLayout(group)
        layout.addWidget(self.status_label)
        return group

    def _clear_tables(self) -> None:
        self.displayed_event_refs = []
        self.displayed_missing_log_refs = []
        self.displayed_expired_task_ids = []
        self.displayed_duration_only_routine_ids = []
        self.displayed_candidate_ids = []
        self.capacity_summary_label.clear()
        self.expired_tasks_summary_label.setText("期限切れAタスクなし")
        self.mark_expired_task_completed_button.setEnabled(False)
        self.mark_expired_task_incomplete_button.setEnabled(False)
        self.missing_logs_summary_label.setText("未入力ログなし")
        self.record_zero_missing_log_button.setEnabled(False)
        self.duration_only_summary_label.clear()
        self.delete_duration_only_button.setEnabled(False)
        self.copy_candidate_to_task_button.setEnabled(False)
        for table in (
            self.events_table,
            self.schedule_overview_table,
            self.expired_tasks_table,
            self.missing_logs_table,
            self.duration_only_table,
            self.candidates_table,
            self.tasks_table,
            self.allocations_table,
        ):
            table.setRowCount(0)

    def _set_events(self, events: list[dict]) -> None:
        rows = []
        self.displayed_event_refs = []

        for event in events:
            rows.append(
                [
                    _event_display_id(event),
                    _event_type_label(event),
                    str(event["title"]),
                    _format_datetime(event["start_dt"]),
                    _format_datetime(event["end_dt"]),
                    str(event.get("note", "")),
                ]
            )
            self.displayed_event_refs.append(_event_ref(event))

        self._set_rows(self.events_table, rows)

    def _build_schedule_overview_entries(
        self,
        start_date: date,
        period_days: int,
    ) -> list[dict]:
        entries = []
        for offset in range(period_days):
            target_date = (start_date + timedelta(days=offset)).isoformat()

            for event in list_events_by_date(target_date):
                if event["type"] != "B":
                    continue
                entries.append(
                    {
                        "date": target_date,
                        "start": _format_datetime(str(event["start_dt"])),
                        "end": _format_datetime(str(event["end_dt"])),
                        "kind": "B",
                        "title": str(event["title"]),
                        "repeat": "単発",
                        "note": str(event.get("note", "")),
                    }
                )

            for routine in list_routine_events_for_date(target_date):
                if routine.get("mode") != "fixed_time":
                    continue
                entries.append(
                    {
                        "date": target_date,
                        "start": _format_datetime(str(routine["start_dt"])),
                        "end": _format_datetime(str(routine["end_dt"])),
                        "kind": "C",
                        "title": str(routine["title"]),
                        "repeat": _routine_repeat_kind(str(routine.get("weekdays", ""))),
                        "note": str(routine.get("note", "")),
                    }
                )

        return sorted(
            entries,
            key=lambda entry: (
                str(entry["date"]),
                str(entry["start"]),
                str(entry["kind"]),
                str(entry["title"]),
            ),
        )

    def _set_schedule_overview(
        self,
        entries: list[dict],
        start_date: str,
        period_days: int,
    ) -> None:
        rows = [
            [
                str(entry["date"]),
                str(entry["start"]),
                str(entry["end"]),
                str(entry["kind"]),
                str(entry["title"]),
                str(entry["repeat"]),
                str(entry["note"]),
            ]
            for entry in entries
        ]
        self._set_rows(self.schedule_overview_table, rows)
        self.schedule_overview_summary_label.setText(
            f"{start_date}から{period_days}日分 / "
            f"B予定・fixed_time C: {len(entries)}件 / "
            "duration_only Cは時刻がないため予定一覧対象外です。"
        )

    def _set_schedule_overview_error(self, message: str) -> None:
        self.schedule_overview_table.setRowCount(0)
        self.schedule_overview_summary_label.setText(message)

    def _set_expired_tasks(self, tasks: list[dict]) -> None:
        self.displayed_expired_task_ids = []
        rows = []

        for task in tasks:
            (
                completed_minutes,
                total_minutes,
                display_percent,
                _bar_percent,
            ) = _task_progress_values(task)
            rows.append(
                [
                    str(task["title"]),
                    str(task["deadline_date"]),
                    str(total_minutes),
                    str(task["remaining_minutes"]),
                    f"{completed_minutes} / {total_minutes}分（{display_percent:.1f}%）",
                ]
            )
            self.displayed_expired_task_ids.append(int(task["id"]))

        self._set_rows(self.expired_tasks_table, rows)
        if rows:
            self.expired_tasks_summary_label.setText(
                f"要確認: 締切超過activeタスク {len(rows)}件"
            )
            self.mark_expired_task_completed_button.setEnabled(True)
            self.mark_expired_task_incomplete_button.setEnabled(True)
            return

        self.expired_tasks_summary_label.setText("期限切れAタスクなし")
        self.mark_expired_task_completed_button.setEnabled(False)
        self.mark_expired_task_incomplete_button.setEnabled(False)

    def _set_missing_logs(self, missing_logs: list[dict]) -> None:
        self.displayed_missing_log_refs = []
        rows = []

        for missing_log in missing_logs:
            rows.append(
                [
                    str(missing_log["log_date"]),
                    str(missing_log["title"]),
                    str(missing_log["planned_minutes"]),
                ]
            )
            self.displayed_missing_log_refs.append(
                (str(missing_log["log_date"]), int(missing_log["a_task_id"]))
            )

        self._set_rows(self.missing_logs_table, rows)
        if rows:
            self.missing_logs_summary_label.setText(
                f"前日のA割当に対する未入力ログ: {len(rows)}件"
            )
            self.record_zero_missing_log_button.setEnabled(True)
            return

        self.missing_logs_summary_label.setText("未入力ログなし")
        self.record_zero_missing_log_button.setEnabled(False)

    def _set_capacity_summary(self, summary: dict) -> None:
        surplus_minutes = int(summary["surplus_minutes"])
        if surplus_minutes < 0:
            surplus_text = f"過密警告: 実質作業可能時間が {abs(surplus_minutes)}分不足"
        else:
            surplus_text = f"余力: {surplus_minutes}分"
        excluded_message = str(summary.get("a_allocation_excluded_message", ""))
        excluded_text = f" / {excluded_message}" if excluded_message else ""

        self.capacity_summary_label.setText(
            f"固定予定後の空き時間合計: {summary['fixed_free_minutes']}分 / "
            f"時間未指定C合計: {summary['floating_c_minutes']}分 / "
            f"実質作業可能時間: {summary['effective_work_minutes']}分 / "
            f"今日のA推奨合計: {summary['total_a_target_minutes']}分 / "
            f"{surplus_text}"
            f"{excluded_text}"
        )

    def _set_duration_only_routines(
        self,
        routines: list[dict],
        total_minutes: int,
    ) -> None:
        self.duration_only_summary_label.setText(f"合計所要時間: {total_minutes}分")
        rows = []
        self.displayed_duration_only_routine_ids = []

        for routine in routines:
            rows.append(
                [
                    f'C{routine["routine_id"]}',
                    str(routine["title"]),
                    str(routine["duration_minutes"]),
                    str(routine.get("note", "")),
                ]
            )
            self.displayed_duration_only_routine_ids.append(int(routine["routine_id"]))

        self._set_rows(self.duration_only_table, rows)
        self.delete_duration_only_button.setEnabled(bool(rows))

    def _set_candidates(self, candidates: list[dict]) -> None:
        self.displayed_candidate_ids = []
        rows = []

        for candidate in candidates:
            rows.append(
                [
                    str(candidate["id"]),
                    str(candidate["title"]),
                    str(candidate.get("category", "")),
                    str(candidate.get("memo", "")),
                    "済" if int(candidate.get("is_converted", 0)) else "未",
                    str(candidate.get("created_at", "")),
                ]
            )
            self.displayed_candidate_ids.append(int(candidate["id"]))

        self._set_rows(self.candidates_table, rows)
        self.copy_candidate_to_task_button.setEnabled(bool(rows))

    def _set_tasks(self, tasks: list[dict]) -> None:
        self.tasks_table.setRowCount(0)
        self.tasks_table.setRowCount(len(tasks))

        for row_index, task in enumerate(tasks):
            (
                completed_minutes,
                total_minutes,
                display_percent,
                bar_percent,
            ) = _task_progress_values(task)
            values = [
                str(task["id"]),
                str(task["title"]),
                _task_scale_label(task),
                str(task.get("start_date", "")),
                str(task["deadline_date"]),
                str(total_minutes),
                str(task["remaining_minutes"]),
                f"{completed_minutes} / {total_minutes}分（{display_percent:.1f}%）",
                "",
                str(task["daily_target_minutes"]),
                str(task.get("schedule_note", "")),
            ]

            for column_index, value in enumerate(values):
                self.tasks_table.setItem(
                    row_index,
                    column_index,
                    QTableWidgetItem(value),
                )

            progress_bar = QProgressBar()
            progress_bar.setRange(0, 100)
            progress_bar.setValue(bar_percent)
            progress_bar.setFormat(f"{display_percent:.1f}%")
            self.tasks_table.setCellWidget(row_index, 8, progress_bar)

    def _set_allocations(self, allocations: list[dict]) -> None:
        rows = [
            [
                _format_datetime(allocation["start"]),
                _format_datetime(allocation["end"]),
                str(allocation["title"]),
                str(allocation["minutes"]),
            ]
            for allocation in allocations
        ]
        self._set_rows(self.allocations_table, rows)

    def _set_log_task_options(self, tasks: list[dict]) -> None:
        current_task_id = self.log_task_input.currentData()
        self.log_task_input.clear()

        if not tasks:
            self.log_task_input.addItem("Aタスクがありません", None)
            self.log_task_input.setEnabled(False)
            return

        self.log_task_input.setEnabled(True)
        for task in tasks:
            label = f'{task["id"]}: {task["title"]}'
            self.log_task_input.addItem(label, int(task["id"]))

        if current_task_id is not None:
            index = self.log_task_input.findData(current_task_id)
            if index >= 0:
                self.log_task_input.setCurrentIndex(index)

    def _set_reminder_targets(
        self,
        events: list[dict],
        allocations: list[dict],
    ) -> None:
        targets: list[dict[str, str]] = []

        for event in events:
            if str(event.get("remind_start", "0")) != "1":
                continue

            start_minute = _datetime_minute_key(str(event["start_dt"]))
            if start_minute is None:
                continue

            targets.append(
                {
                    "key": f'{_event_source(event)}:{_event_ref_id(event)}:{start_minute}',
                    "start_minute": start_minute,
                    "message": f'B/C予定「{event["title"]}」が始まります。',
                }
            )

        for allocation in allocations:
            start_minute = _datetime_minute_key(str(allocation["start"]))
            if start_minute is None:
                continue

            targets.append(
                {
                    "key": f'a:{allocation["a_task_id"]}:{start_minute}',
                    "start_minute": start_minute,
                    "message": f'Aタスク「{allocation["title"]}」を開始する時間です。',
                }
            )

        self.reminder_targets = targets
        self._update_reminder_summary()

    def _set_rows(self, table: QTableWidget, rows: list[list[str]]) -> None:
        table.setRowCount(len(rows))
        for row_index, row in enumerate(rows):
            for column_index, value in enumerate(row):
                table.setItem(row_index, column_index, QTableWidgetItem(value))

    def _selected_row_id(self, table: QTableWidget) -> int | None:
        row = table.currentRow()
        if row < 0:
            return None

        item = table.item(row, 0)
        if item is None:
            return None

        try:
            return int(item.text())
        except ValueError:
            return None

    def _selected_event_ref(self) -> tuple[str, int] | None:
        row = self.events_table.currentRow()
        if row < 0 or row >= len(self.displayed_event_refs):
            return None
        return self.displayed_event_refs[row]

    def _selected_missing_log_ref(self) -> tuple[str, int] | None:
        row = self.missing_logs_table.currentRow()
        if row < 0 or row >= len(self.displayed_missing_log_refs):
            return None
        return self.displayed_missing_log_refs[row]

    def _selected_duration_only_routine_id(self) -> int | None:
        row = self.duration_only_table.currentRow()
        if row < 0 or row >= len(self.displayed_duration_only_routine_ids):
            return None
        return self.displayed_duration_only_routine_ids[row]

    def _selected_candidate_id(self) -> int | None:
        row = self.candidates_table.currentRow()
        if row < 0 or row >= len(self.displayed_candidate_ids):
            return None
        return self.displayed_candidate_ids[row]

    def _selected_expired_task_id(self) -> int | None:
        row = self.expired_tasks_table.currentRow()
        if row < 0 or row >= len(self.displayed_expired_task_ids):
            return None
        return self.displayed_expired_task_ids[row]

    def _build_missing_logs_for_previous_day(self, tasks: list[dict]) -> list[dict]:
        previous_date = (
            date.fromisoformat(self.target_date) - timedelta(days=1)
        ).isoformat()
        allocations = self._build_allocations_for_date(
            previous_date,
            _tasks_available_on_date(tasks, previous_date),
        )
        planned_by_task: dict[int, dict] = {}

        for allocation in allocations:
            a_task_id = int(allocation["a_task_id"])
            planned = planned_by_task.setdefault(
                a_task_id,
                {
                    "log_date": previous_date,
                    "a_task_id": a_task_id,
                    "title": str(allocation["title"]),
                    "planned_minutes": 0,
                },
            )
            planned["planned_minutes"] += int(allocation["minutes"])

        missing_logs = []
        for planned in planned_by_task.values():
            if has_daily_log(previous_date, int(planned["a_task_id"])):
                continue
            missing_logs.append(planned)

        return sorted(
            missing_logs,
            key=lambda item: (str(item["log_date"]), str(item["title"]), int(item["a_task_id"])),
        )

    def _build_allocations_for_date(
        self,
        target_date: str,
        tasks: list[dict],
    ) -> list[dict]:
        events = [
            dict(event, source="event")
            for event in list_events_by_date(target_date)
            if event["type"] == "B"
        ]
        routine_events = list_routine_events_for_date(target_date)
        fixed_time_routines = [
            event for event in routine_events
            if event.get("mode") == "fixed_time"
        ]
        scheduled_events = sorted(
            events + fixed_time_routines,
            key=lambda event: (str(event.get("start_dt", "")), _event_display_id(event)),
        )
        busy_blocks = build_busy_blocks(scheduled_events)
        free_blocks = build_free_blocks(target_date, busy_blocks)
        return allocate_tasks_to_free_blocks(
            tasks=tasks,
            free_blocks=free_blocks,
            today=target_date,
        )

    def _confirm_delete(self, target: str) -> bool:
        result = QMessageBox.question(
            self,
            "削除確認",
            f"{target}を削除しますか？",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        return result == QMessageBox.StandardButton.Yes

    def _validate_a_task_input(
        self,
        title: str,
        start_date: str,
        deadline_date: str,
        total_minutes_text: str,
    ) -> str | None:
        if not title:
            return "タイトルを入力してください。"
        if not start_date:
            return "開始日を入力してください。"
        if not deadline_date:
            return "締切日を入力してください。"
        if not total_minutes_text:
            return "必要時間を入力してください。"

        try:
            parsed_start = date.fromisoformat(start_date)
        except ValueError:
            return "開始日はYYYY-MM-DD形式で入力してください。"

        try:
            parsed_deadline = date.fromisoformat(deadline_date)
        except ValueError:
            return "締切日はYYYY-MM-DD形式で入力してください。"

        if parsed_start > parsed_deadline:
            return "開始日は締切日以前にしてください。"

        try:
            total_minutes = int(total_minutes_text)
        except ValueError:
            return "必要時間は整数で入力してください。"

        if total_minutes <= 0:
            return "必要時間は1分以上で入力してください。"

        return None

    def _validate_candidate_input(self, title: str) -> str | None:
        if not title:
            return "Aタスク候補メモのタイトルを入力してください。"
        return None

    def _validate_task_total_update_input(
        self,
        a_task_id: int | None,
        new_total_minutes_text: str,
    ) -> str | None:
        if a_task_id is None:
            return "更新するAタスクを選択してください。"
        if not new_total_minutes_text:
            return "新しい想定総時間を入力してください。"

        try:
            new_total_minutes = int(new_total_minutes_text)
        except ValueError:
            return "新しい想定総時間は整数で入力してください。"

        if new_total_minutes <= 0:
            return "新しい想定総時間は1分以上で入力してください。"

        return None

    def _validate_b_event_input(
        self,
        title: str,
        start_dt: str,
        end_dt: str,
        note: str,
    ) -> str | None:
        if not title:
            return "B予定タイトルを入力してください。"
        if not start_dt:
            return "開始日時を入力してください。"
        if not end_dt:
            return "終了日時を入力してください。"
        if not note:
            return "メモを入力してください。"

        start = _parse_event_datetime(start_dt)
        end = _parse_event_datetime(end_dt)
        if start is None or end is None:
            return "日時はYYYY-MM-DDTHH:MM:SS形式で入力してください。"
        if start >= end:
            return "開始日時は終了日時より前にしてください。"

        return None

    def _validate_routine_event_input(
        self,
        title: str,
        mode: str,
        start_time: str,
        end_time: str,
        duration_minutes_text: str,
    ) -> str | None:
        if not title:
            return "Cルールタイトルを入力してください。"
        if mode not in ("fixed_time", "duration_only"):
            return "modeはfixed_timeまたはduration_onlyを選んでください。"

        if mode == "fixed_time":
            if not start_time:
                return "開始時刻を入力してください。"
            if not end_time:
                return "終了時刻を入力してください。"

            start = _parse_routine_time(start_time)
            end = _parse_routine_time(end_time)
            if start is None or end is None:
                return "時刻はHH:MM形式で入力してください。"
            if start >= end:
                return "開始時刻は終了時刻より前にしてください。"

        if mode == "duration_only":
            if not duration_minutes_text:
                return "所要時間を入力してください。"

            try:
                duration_minutes = int(duration_minutes_text)
            except ValueError:
                return "所要時間は整数で入力してください。"

            if duration_minutes <= 0:
                return "所要時間は1分以上で入力してください。"

        return None

    def _validate_daily_log_input(
        self,
        a_task_id: int | None,
        log_date: str,
        actual_minutes_text: str,
        reflection: str,
    ) -> str | None:
        if a_task_id is None:
            return "Aタスクが存在しません。"
        if not log_date:
            return "ログ日付を入力してください。"
        if not actual_minutes_text:
            return "実績時間を入力してください。"
        if not reflection:
            return "反省テキストを入力してください。"

        try:
            date.fromisoformat(log_date)
        except ValueError:
            return "ログ日付はYYYY-MM-DD形式で入力してください。"

        try:
            actual_minutes = int(actual_minutes_text)
        except ValueError:
            return "実績時間は整数で入力してください。"

        if actual_minutes < 0:
            return "実績時間は0分以上で入力してください。"

        return None

    def _load_check_reminder_settings(self) -> None:
        try:
            morning_time = get_setting(
                MORNING_CHECK_TIME_KEY,
                DEFAULT_MORNING_CHECK_TIME,
            )
            night_time = get_setting(
                NIGHT_LOG_TIME_KEY,
                DEFAULT_NIGHT_LOG_TIME,
            )
        except Exception:
            morning_time = DEFAULT_MORNING_CHECK_TIME
            night_time = DEFAULT_NIGHT_LOG_TIME

        self.morning_check_time = (
            _normalize_hhmm(morning_time) or DEFAULT_MORNING_CHECK_TIME
        )
        self.night_log_time = (
            _normalize_hhmm(night_time) or DEFAULT_NIGHT_LOG_TIME
        )
        self.morning_check_time_input.setText(self.morning_check_time)
        self.night_log_time_input.setText(self.night_log_time)
        self._update_reminder_summary()

    def _update_reminder_summary(self) -> None:
        self.reminder_summary_label.setText(
            f"朝の予定確認: {self.morning_check_time} / "
            f"夜のログ入力確認: {self.night_log_time} / "
            f"現在のリマインド対象: {len(self.reminder_targets)}件"
        )

    def _clear_event_inputs(self) -> None:
        self.event_title_input.clear()
        self.event_start_input.setText(f"{self.target_date}T09:00:00")
        self.event_end_input.setText(f"{self.target_date}T10:00:00")
        self.event_remind_start_input.setChecked(False)
        self.event_remind_end_input.setChecked(False)
        self.event_note_input.clear()

    def _clear_candidate_inputs(self) -> None:
        self.candidate_title_input.clear()
        self.candidate_memo_input.clear()
        self.candidate_category_input.clear()

    def _sync_target_date_inputs(self, old_target_date: str | None = None) -> None:
        self.log_date_input.setText(self.target_date)

        task_start = self.task_start_input.text().strip()
        if not task_start or task_start == old_target_date:
            self.task_start_input.setText(self.target_date)

        task_deadline = self.task_deadline_input.text().strip()
        if not task_deadline or task_deadline == old_target_date:
            self.task_deadline_input.setText(self.target_date)

        schedule_start = self.schedule_start_input.text().strip()
        if not schedule_start or schedule_start == old_target_date:
            self.schedule_start_input.setText(self.target_date)

        self._sync_datetime_input_date(
            self.event_start_input,
            old_target_date,
            "09:00:00",
        )
        self._sync_datetime_input_date(
            self.event_end_input,
            old_target_date,
            "10:00:00",
        )
        self._update_routine_repeat_hint()

    def _sync_datetime_input_date(
        self,
        input_widget: QLineEdit,
        old_target_date: str | None,
        default_time: str,
    ) -> None:
        value = input_widget.text().strip()
        if not value:
            input_widget.setText(f"{self.target_date}T{default_time}")
            return

        if old_target_date and value.startswith(f"{old_target_date}T"):
            input_widget.setText(f"{self.target_date}{value[len(old_target_date):]}")

    def _clear_routine_inputs(self) -> None:
        self.routine_mode_input.setCurrentIndex(0)
        self.routine_title_input.clear()
        self.routine_start_input.clear()
        self.routine_end_input.clear()
        self.routine_duration_input.clear()
        self.routine_everyday_input.setChecked(True)
        self.routine_weekly_input.setChecked(False)
        self._clear_routine_weekday_inputs()
        self._set_routine_weekday_inputs_enabled(False)
        self.routine_remind_start_input.setChecked(False)
        self.routine_remind_end_input.setChecked(False)
        self.routine_note_input.clear()
        self._update_routine_mode_inputs()
        self._update_routine_repeat_hint()

    def _update_routine_mode_inputs(self) -> None:
        is_fixed_time = self.routine_mode_input.currentText().strip() == "fixed_time"
        self.routine_start_input.setEnabled(is_fixed_time)
        self.routine_end_input.setEnabled(is_fixed_time)
        self.routine_remind_start_input.setEnabled(is_fixed_time)
        self.routine_remind_end_input.setEnabled(is_fixed_time)
        self.routine_duration_input.setEnabled(not is_fixed_time)

    def _on_routine_everyday_toggled(self, checked: bool) -> None:
        if checked and self.routine_weekly_input.isChecked():
            self.routine_weekly_input.setChecked(False)
        self._set_routine_weekday_inputs_enabled(self.routine_weekly_input.isChecked())
        self._update_routine_repeat_hint()

    def _on_routine_weekly_toggled(self, checked: bool) -> None:
        if checked and self.routine_everyday_input.isChecked():
            self.routine_everyday_input.setChecked(False)
        self._set_routine_weekday_inputs_enabled(checked)
        if checked and not self._selected_routine_weekdays():
            self._select_current_target_weekday()
        self._update_routine_repeat_hint()

    def _update_routine_repeat_hint(self) -> None:
        if self.routine_everyday_input.isChecked():
            self.routine_repeat_hint_label.setText("繰り返し: 毎日")
            return

        if self.routine_weekly_input.isChecked():
            selected_weekdays = self._selected_routine_weekdays()
            weekday_labels = ", ".join(
                _format_weekday_label(weekday) for weekday in selected_weekdays
            )
            if not weekday_labels:
                weekday_labels = "曜日未選択"
            self.routine_repeat_hint_label.setText(
                f"繰り返し: 毎週（{weekday_labels}）"
            )
            return

        self.routine_repeat_hint_label.setText("繰り返しを選択してください")

    def _validate_routine_repeat_setting(self) -> str | None:
        everyday_checked = self.routine_everyday_input.isChecked()
        weekly_checked = self.routine_weekly_input.isChecked()
        if everyday_checked and weekly_checked:
            return "毎日繰り返すと毎週繰り返すは同時に選択できません。"
        if not everyday_checked and not weekly_checked:
            return "毎日繰り返すか毎週繰り返すのどちらかを選択してください。"
        if weekly_checked and not self._selected_routine_weekdays():
            return "毎週繰り返す場合は曜日を1つ以上選択してください。"
        return None

    def _routine_weekdays_from_repeat_setting(self) -> str:
        if self.routine_everyday_input.isChecked():
            return EVERYDAY_WEEKDAYS

        if self.routine_weekly_input.isChecked():
            selected_weekdays = self._selected_routine_weekdays()
            if selected_weekdays:
                return ",".join(str(weekday) for weekday in selected_weekdays)

        raise ValueError("繰り返し設定が未選択です。")

    def _selected_routine_weekdays(self) -> list[int]:
        return [
            weekday
            for weekday, input_widget in enumerate(self.routine_weekday_inputs)
            if input_widget.isChecked()
        ]

    def _clear_routine_weekday_inputs(self) -> None:
        for weekday_input in self.routine_weekday_inputs:
            weekday_input.setChecked(False)

    def _set_routine_weekday_inputs_enabled(self, enabled: bool) -> None:
        for weekday_input in self.routine_weekday_inputs:
            weekday_input.setEnabled(enabled)

    def _select_current_target_weekday(self) -> None:
        weekday = date.fromisoformat(self.target_date).weekday()
        if 0 <= weekday < len(self.routine_weekday_inputs):
            self.routine_weekday_inputs[weekday].setChecked(True)

    def _clear_daily_log_inputs(self) -> None:
        self.log_date_input.setText(self.target_date)
        self.log_minutes_input.clear()
        self.log_reflection_input.clear()


def _format_datetime(value: str) -> str:
    # MVPでは同一日の一覧表示なので、表では時刻だけを読みやすく見せる。
    return value[11:16] if "T" in value and len(value) >= 16 else value


def _parse_event_datetime(value: str) -> datetime | None:
    try:
        return datetime.strptime(value, "%Y-%m-%dT%H:%M:%S")
    except ValueError:
        return None


def _format_weekday_label(weekday: int) -> str:
    if 0 <= weekday < len(WEEKDAY_LABELS):
        return WEEKDAY_LABELS[weekday]
    return str(weekday)


def _routine_repeat_kind(weekdays: str) -> str:
    parts = [part.strip() for part in weekdays.split(",") if part.strip()]
    return "毎日" if ",".join(parts) == EVERYDAY_WEEKDAYS else "毎週"


def _parse_routine_time(value: str) -> time | None:
    try:
        return datetime.strptime(value.strip(), "%H:%M").time()
    except ValueError:
        return None


def _normalize_hhmm(value: str | None) -> str | None:
    if value is None:
        return None

    text = value.strip()
    if len(text) != 5 or text[2] != ":":
        return None

    try:
        parsed = datetime.strptime(text, "%H:%M")
    except ValueError:
        return None

    normalized = parsed.strftime("%H:%M")
    return normalized if normalized == text else None


def _datetime_minute_key(value: str) -> str | None:
    parsed = _parse_event_datetime(value)
    if parsed is None:
        return None
    return parsed.strftime("%Y-%m-%dT%H:%M")


def _task_progress_values(task: dict) -> tuple[int, int, float, int]:
    total_minutes = int(task.get("total_minutes", 0))
    remaining_minutes = int(task.get("remaining_minutes", 0))
    if total_minutes <= 0:
        return (0, 0, 0.0, 0)

    completed_minutes = max(total_minutes - remaining_minutes, 0)
    progress = (total_minutes - remaining_minutes) / total_minutes * 100
    progress = max(0.0, min(progress, 100.0))
    display_percent = int(progress * 10 + 0.5) / 10
    bar_percent = int(progress)
    return (completed_minutes, total_minutes, display_percent, bar_percent)


def _task_scale_label(task: dict) -> str:
    label = str(task.get("task_scale_label", "other"))
    return TASK_SCALE_LABELS.get(label, TASK_SCALE_LABELS["other"])


def _tasks_available_on_date(tasks: list[dict], target_date: str) -> list[dict]:
    return [
        task
        for task in tasks
        if str(task["deadline_date"]) >= target_date
    ]


def _event_source(event: dict) -> str:
    return str(event.get("source", "event"))


def _event_ref_id(event: dict) -> int:
    if _event_source(event) == "routine":
        return int(event["routine_id"])
    return int(event["id"])


def _event_ref(event: dict) -> tuple[str, int]:
    return (_event_source(event), _event_ref_id(event))


def _event_display_id(event: dict) -> str:
    prefix = "C" if _event_source(event) == "routine" else "B"
    return f"{prefix}{_event_ref_id(event)}"


def _event_type_label(event: dict) -> str:
    if _event_source(event) == "routine":
        return "C(fixed_time)"
    return str(event["type"])

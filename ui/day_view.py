from __future__ import annotations

from datetime import date, datetime

from PySide6.QtCore import Qt, QTimer
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
    QPushButton,
    QSplitter,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from core.scheduler import (
    allocate_tasks_to_free_blocks,
    attach_daily_targets_to_tasks,
    build_busy_blocks,
    build_free_blocks,
)
from data.db import (
    delete_a_task,
    delete_event,
    insert_a_task,
    insert_event,
    list_a_tasks,
    list_events_by_date,
    recompute_remaining_minutes,
    upsert_daily_log,
)


FIXED_TARGET_DATE = "2026-04-20"


class DayView(QWidget):
    def __init__(self, target_date: str = FIXED_TARGET_DATE) -> None:
        super().__init__()
        self.target_date = target_date
        self.reminder_targets: list[dict[str, str]] = []
        self.notified_reminder_keys: set[str] = set()

        self.date_label = QLabel()
        self.target_date_input = QLineEdit(self.target_date)
        self.change_date_button = QPushButton("日付変更")
        self.refresh_button = QPushButton("再計算")
        self.status_label = QLabel()
        self.task_title_input = QLineEdit()
        self.task_deadline_input = QLineEdit()
        self.task_minutes_input = QLineEdit()
        self.add_task_button = QPushButton("Aタスク追加")
        self.event_type_input = QComboBox()
        self.event_title_input = QLineEdit()
        self.event_start_input = QLineEdit()
        self.event_end_input = QLineEdit()
        self.event_remind_start_input = QCheckBox()
        self.event_remind_end_input = QCheckBox()
        self.event_note_input = QLineEdit()
        self.add_event_button = QPushButton("B/Cイベント追加")
        self.log_task_input = QComboBox()
        self.log_date_input = QLineEdit(self.target_date)
        self.log_minutes_input = QLineEdit()
        self.log_reflection_input = QLineEdit()
        self.save_log_button = QPushButton("日次ログ保存")
        self.delete_task_button = QPushButton("選択Aタスク削除")
        self.delete_event_button = QPushButton("選択B/Cイベント削除")

        self.events_table = self._create_table(["ID", "種別", "タイトル", "開始", "終了", "メモ"])
        self.tasks_table = self._create_table(
            ["ID", "タイトル", "締切", "残り(分)", "今日の目標(分)"]
        )
        self.allocations_table = self._create_table(
            ["AタスクID", "タイトル", "開始", "終了", "分"]
        )

        self._build_layout()
        self.change_date_button.clicked.connect(self.refresh)
        self.refresh_button.clicked.connect(self.refresh)
        self.add_task_button.clicked.connect(self.add_a_task)
        self.add_event_button.clicked.connect(self.add_event)
        self.save_log_button.clicked.connect(self.save_daily_log)
        self.delete_task_button.clicked.connect(self.delete_selected_task)
        self.delete_event_button.clicked.connect(self.delete_selected_event)
        self.refresh()
        self.reminder_timer = QTimer(self)
        self.reminder_timer.setInterval(60_000)
        self.reminder_timer.timeout.connect(self.check_reminders)
        self.reminder_timer.start()

    def _build_layout(self) -> None:
        root = QVBoxLayout(self)

        header = QHBoxLayout()
        header.addWidget(self.date_label)
        header.addStretch(1)
        header.addWidget(QLabel("対象日付"))
        header.addWidget(self.target_date_input)
        header.addWidget(self.change_date_button)
        header.addWidget(self.refresh_button)
        root.addLayout(header)

        forms = QHBoxLayout()
        forms.addWidget(self._build_add_task_form())
        forms.addWidget(self._build_add_event_form())
        forms.addWidget(self._build_daily_log_form())
        root.addLayout(forms)

        delete_actions = QHBoxLayout()
        delete_actions.addStretch(1)
        delete_actions.addWidget(self.delete_task_button)
        delete_actions.addWidget(self.delete_event_button)
        root.addLayout(delete_actions)

        splitter = QSplitter(Qt.Vertical)
        splitter.addWidget(self._wrap_table("B/C予定一覧", self.events_table))
        splitter.addWidget(self._wrap_table("Aタスク一覧", self.tasks_table))
        splitter.addWidget(self._wrap_table("A割当結果一覧", self.allocations_table))
        root.addWidget(splitter, 1)
        root.addWidget(self.status_label)

    def refresh(self) -> None:
        error = self._apply_target_date_from_input()
        if error:
            self.status_label.setText(error)
            return

        self.date_label.setText(f"日付: {self.target_date}")

        try:
            events = list_events_by_date(self.target_date)
            busy_blocks = build_busy_blocks(events)
            free_blocks = build_free_blocks(self.target_date, busy_blocks)
            tasks = list_a_tasks()
            tasks_with_targets = attach_daily_targets_to_tasks(tasks, today=self.target_date)
            allocations = allocate_tasks_to_free_blocks(
                tasks=tasks,
                free_blocks=free_blocks,
                today=self.target_date,
            )
        except Exception as exc:
            self._clear_tables()
            self.status_label.setText(f"読み込みに失敗しました: {exc}")
            return

        self._set_events(events)
        self._set_tasks(tasks_with_targets)
        self._set_allocations(allocations)
        self._set_log_task_options(tasks)
        self._set_reminder_targets(events, allocations)
        self.status_label.setText(
            f"B/C予定 {len(events)}件 / Aタスク {len(tasks)}件 / 割当 {len(allocations)}件"
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
            self.target_date = target_date
            self.log_date_input.setText(target_date)

        return None

    def add_a_task(self) -> None:
        title = self.task_title_input.text().strip()
        deadline_date = self.task_deadline_input.text().strip()
        total_minutes_text = self.task_minutes_input.text().strip()

        error = self._validate_a_task_input(title, deadline_date, total_minutes_text)
        if error:
            self.status_label.setText(error)
            return

        try:
            total_minutes = int(total_minutes_text)
            insert_a_task(
                title=title,
                deadline_date=deadline_date,
                total_minutes=total_minutes,
            )
        except Exception as exc:
            self.status_label.setText(f"Aタスクの保存に失敗しました: {exc}")
            return

        self.task_title_input.clear()
        self.task_deadline_input.clear()
        self.task_minutes_input.clear()
        self.refresh()
        self.status_label.setText("Aタスクを追加しました。")

    def add_event(self) -> None:
        event_type = self.event_type_input.currentText().strip()
        title = self.event_title_input.text().strip()
        start_dt = self.event_start_input.text().strip()
        end_dt = self.event_end_input.text().strip()
        note = self.event_note_input.text().strip()

        error = self._validate_event_input(event_type, title, start_dt, end_dt, note)
        if error:
            self.status_label.setText(error)
            return

        try:
            insert_event(
                event_type=event_type,
                title=title,
                start_dt=start_dt,
                end_dt=end_dt,
                remind_start=int(self.event_remind_start_input.isChecked()),
                remind_end=int(self.event_remind_end_input.isChecked()),
                note=note,
            )
        except Exception as exc:
            self.status_label.setText(f"B/Cイベントの保存に失敗しました: {exc}")
            return

        self._clear_event_inputs()
        self.refresh()
        self.status_label.setText("B/Cイベントを追加しました。")

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
        event_id = self._selected_row_id(self.events_table)
        if event_id is None:
            self.status_label.setText("削除するB/Cイベントを選択してください。")
            return

        if not self._confirm_delete("選択したB/Cイベント"):
            return

        try:
            delete_event(event_id)
        except Exception as exc:
            self.status_label.setText(f"B/Cイベントの削除に失敗しました: {exc}")
            return

        self.refresh()
        self.status_label.setText("B/Cイベントを削除しました。")

    def check_reminders(self) -> None:
        current_minute = datetime.now().strftime("%Y-%m-%dT%H:%M")
        messages = []

        for target in self.reminder_targets:
            if target["start_minute"] != current_minute:
                continue
            if target["key"] in self.notified_reminder_keys:
                continue

            self.notified_reminder_keys.add(target["key"])
            messages.append(target["message"])

        if messages:
            self.status_label.setText("リマインド: " + " / ".join(messages))

    def _build_add_task_form(self) -> QGroupBox:
        group = QGroupBox("Aタスク追加")
        form = QFormLayout(group)

        self.task_title_input.setPlaceholderText("例: レポート作成")
        self.task_deadline_input.setPlaceholderText("YYYY-MM-DD")
        self.task_minutes_input.setPlaceholderText("例: 120")

        form.addRow("タイトル", self.task_title_input)
        form.addRow("締切日", self.task_deadline_input)
        form.addRow("必要時間(分)", self.task_minutes_input)
        form.addRow(self.add_task_button)
        return group

    def _build_add_event_form(self) -> QGroupBox:
        group = QGroupBox("B/Cイベント追加")
        form = QFormLayout(group)

        self.event_type_input.addItems(["B", "C"])
        self.event_title_input.setPlaceholderText("例: ゼミ")
        self.event_start_input.setPlaceholderText("YYYY-MM-DDTHH:MM:SS")
        self.event_end_input.setPlaceholderText("YYYY-MM-DDTHH:MM:SS")
        self.event_note_input.setPlaceholderText("例: 研究室")

        form.addRow("種別", self.event_type_input)
        form.addRow("タイトル", self.event_title_input)
        form.addRow("開始日時", self.event_start_input)
        form.addRow("終了日時", self.event_end_input)
        form.addRow("開始リマインド", self.event_remind_start_input)
        form.addRow("終了リマインド", self.event_remind_end_input)
        form.addRow("メモ", self.event_note_input)
        form.addRow(self.add_event_button)
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

    def _wrap_table(self, title: str, table: QTableWidget) -> QGroupBox:
        group = QGroupBox(title)
        layout = QVBoxLayout(group)
        layout.addWidget(table)
        return group

    def _clear_tables(self) -> None:
        for table in (self.events_table, self.tasks_table, self.allocations_table):
            table.setRowCount(0)

    def _set_events(self, events: list[dict]) -> None:
        rows = [
            [
                str(event["id"]),
                str(event["type"]),
                str(event["title"]),
                _format_datetime(event["start_dt"]),
                _format_datetime(event["end_dt"]),
                str(event.get("note", "")),
            ]
            for event in events
        ]
        self._set_rows(self.events_table, rows)

    def _set_tasks(self, tasks: list[dict]) -> None:
        rows = [
            [
                str(task["id"]),
                str(task["title"]),
                str(task["deadline_date"]),
                str(task["remaining_minutes"]),
                str(task["daily_target_minutes"]),
            ]
            for task in tasks
        ]
        self._set_rows(self.tasks_table, rows)

    def _set_allocations(self, allocations: list[dict]) -> None:
        rows = [
            [
                str(allocation["a_task_id"]),
                str(allocation["title"]),
                _format_datetime(allocation["start"]),
                _format_datetime(allocation["end"]),
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
                    "key": f'event:{event["id"]}:{start_minute}',
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
        deadline_date: str,
        total_minutes_text: str,
    ) -> str | None:
        if not title:
            return "タイトルを入力してください。"
        if not deadline_date:
            return "締切日を入力してください。"
        if not total_minutes_text:
            return "必要時間を入力してください。"

        try:
            date.fromisoformat(deadline_date)
        except ValueError:
            return "締切日はYYYY-MM-DD形式で入力してください。"

        try:
            total_minutes = int(total_minutes_text)
        except ValueError:
            return "必要時間は整数で入力してください。"

        if total_minutes <= 0:
            return "必要時間は1分以上で入力してください。"

        return None

    def _validate_event_input(
        self,
        event_type: str,
        title: str,
        start_dt: str,
        end_dt: str,
        note: str,
    ) -> str | None:
        if not event_type:
            return "種別を入力してください。"
        if event_type not in ("B", "C"):
            return "種別はBまたはCを選んでください。"
        if not title:
            return "イベントタイトルを入力してください。"
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

    def _clear_event_inputs(self) -> None:
        self.event_type_input.setCurrentIndex(0)
        self.event_title_input.clear()
        self.event_start_input.clear()
        self.event_end_input.clear()
        self.event_remind_start_input.setChecked(False)
        self.event_remind_end_input.setChecked(False)
        self.event_note_input.clear()

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


def _datetime_minute_key(value: str) -> str | None:
    parsed = _parse_event_datetime(value)
    if parsed is None:
        return None
    return parsed.strftime("%Y-%m-%dT%H:%M")

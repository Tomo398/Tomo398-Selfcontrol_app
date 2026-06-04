from __future__ import annotations

from PySide6.QtWidgets import QMainWindow

from ui.day_view import DayView


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("Selfcontrol Planner")
        self.resize(960, 720)
        self.setCentralWidget(DayView())

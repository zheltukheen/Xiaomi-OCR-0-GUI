"""Journal window (separate top-level window)."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QPlainTextEdit, QVBoxLayout, QWidget


class LogWindow(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowFlag(Qt.WindowStaysOnTopHint, False)
        self.setWindowTitle("Journal")
        self.resize(760, 420)
        lay = QVBoxLayout(self)
        self.edit = QPlainTextEdit()
        self.edit.setReadOnly(True)
        self.edit.setMaximumBlockCount(5000)
        lay.addWidget(self.edit)

    def append(self, line: str):
        self.edit.appendPlainText(line)

    def is_empty(self) -> bool:
        return self.edit.toPlainText() == ""

"""Dialogs: export format choice and multi-file open choice."""

from __future__ import annotations

import os

from PySide6.QtWidgets import (
    QCheckBox, QComboBox, QDialog, QDialogButtonBox, QFileDialog, QGridLayout,
    QHBoxLayout, QLabel, QLineEdit, QPushButton, QRadioButton, QVBoxLayout,
)

from ..exporters import EXPORT_FORMATS


class ExportDialog(QDialog):
    """Choose which formats to export the current document to, and where."""

    def __init__(self, default_dir: str | None = None, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Export recognized text")
        lay = QVBoxLayout(self)
        lay.addWidget(QLabel("Formats to export:"))

        grid = QGridLayout()
        self.boxes: list[QCheckBox] = []
        for i, fmt in enumerate(EXPORT_FORMATS):
            cb = QCheckBox(fmt.upper())
            grid.addWidget(cb, i // 5, i % 5)
            self.boxes.append(cb)
        lay.addLayout(grid)

        row = QHBoxLayout()
        row.addWidget(QLabel("Save to:"))
        self.dir_edit = QLineEdit(default_dir or "")
        browse = QPushButton("Browse…")
        browse.clicked.connect(self._browse)
        row.addWidget(self.dir_edit, 1)
        row.addWidget(browse)
        lay.addLayout(row)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        lay.addWidget(buttons)
        self.setMinimumWidth(420)

    def _browse(self):
        d = QFileDialog.getExistingDirectory(self, "Choose folder", self.dir_edit.text() or "")
        if d:
            self.dir_edit.setText(d)

    def selected_formats(self) -> list[str]:
        return [cb.text().lower() for cb in self.boxes if cb.isChecked()]

    @staticmethod
    def get(formats: list[str], out_dir: str, parent=None) -> bool:
        """Static convenience: fill the dialog; returns accepted?"""
        dlg = ExportDialog(default_dir=out_dir, parent=parent)
        for cb in dlg.boxes:
            cb.setChecked(cb.text() in formats)
        return dlg.exec() == QDialog.Accepted

    def out_dir(self) -> str:
        return self.dir_edit.text().strip() or "."


class BatchOpenDialog(QDialog):
    """What to do with several files opened at once:
    open each in a tab and recognize, or recognize and export to a format."""

    def __init__(self, count: int, parent=None):
        super().__init__(parent)
        self.setWindowTitle(f"{count} files opened")
        lay = QVBoxLayout(self)
        lay.addWidget(QLabel(
            f"You opened {count} files. What should be done with them?"
        ))

        self.radio_tabs = QRadioButton("Recognize each file in its own tab")
        self.radio_tabs.setChecked(True)
        self.radio_export = QRadioButton("Recognize and export to one format:")
        lay.addWidget(self.radio_tabs)
        lay.addWidget(self.radio_export)

        row = QHBoxLayout()
        self.format_combo = QComboBox()
        for fmt in EXPORT_FORMATS:
            self.format_combo.addItem(fmt.upper(), userData=fmt)
        self.format_combo.setCurrentText("MD")
        self.out_edit = QLineEdit("")
        self.browse = QPushButton("Folder…")
        self.browse.clicked.connect(self._browse)
        row.addWidget(self.format_combo)
        row.addWidget(self.out_edit, 1)
        row.addWidget(self.browse)
        lay.addLayout(row)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        lay.addWidget(buttons)
        self.setMinimumWidth(440)

    def _browse(self):
        d = QFileDialog.getExistingDirectory(self, "Choose folder", self.out_edit.text() or "")
        if d:
            self.out_edit.setText(d)

    def mode(self) -> str:
        return "tabs" if self.radio_tabs.isChecked() else "export"

    def export_format(self) -> str:
        return self.format_combo.currentData()

    def out_dir(self) -> str:
        return self.out_edit.text().strip() or "."

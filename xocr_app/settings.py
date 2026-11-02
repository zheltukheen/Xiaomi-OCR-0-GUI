"""Сохранение настроек через QSettings."""

from PySide6.QtCore import QSettings

_DEFAULTS = {
    "dpi": 200,
    "task": "Full document parsing",
    "device": "auto",
    "question": "",
}


class AppSettings:
    def __init__(self):
        self.q = QSettings("xiaomi-ocr", "app")

    def get(self, key, default=None):
        return self.q.value(key, _DEFAULTS.get(key, default))

    def set(self, key, value):
        self.q.setValue(key, value)

    def dpi(self) -> int:
        try:
            return int(self.get("dpi", 200))
        except (TypeError, ValueError):
            return 200

    def task(self) -> str:
        task = str(self.get("task") or "Full document parsing")
        if task not in ("Full document parsing", "Text only", "Recognize table", "Recognize formula", "Ask a question (VQA)"):
            return "Full document parsing"
        return task

    def device(self) -> str:
        device = str(self.get("device") or "auto")
        return device if device in ("auto", "cuda", "mps", "cpu") else "auto"

    def question(self) -> str:
        return str(self.get("question", ""))


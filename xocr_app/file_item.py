"""State of one opened file."""

from __future__ import annotations

import os


class FileItem:
    def __init__(self, path: str, kind: str = "ocr"):
        self.path = path
        self.kind = kind          # "ocr" | "text"
        self.state = "queued"     # queued | recognizing | done | error | stopped
        self.result = None        # exporters.OcrText
        self.images: list[str] | None = None
        self.job = None           # active Job

    def ensure_result(self):
        from .exporters import OcrText
        if self.result is None:
            self.result = OcrText(source_path=self.path, full_text="", pages=[])
        return self.result

    def display(self) -> str:
        return os.path.basename(self.path)

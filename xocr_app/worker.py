"""Background recognition worker with a job queue.

Jobs are processed one at a time. The worker can be stopped entirely
(clears pending jobs and stops after the current page) and individual jobs
can be cancelled while they wait in the queue.
"""

from __future__ import annotations

import threading
import traceback
from collections import deque

from PySide6.QtCore import Signal, QThread

from .exporters import OcrText, export_text
from .ingest import IngestError, ingest
from .model_engine import format_exception, get_engine
from .model_manager import MODEL_FAILED, MODEL_READY


class Job:
    __slots__ = ("item", "task", "question", "dpi", "export_formats", "out_dir")

    def __init__(self, item, task: str, question: str = "", dpi: int = 200,
                 export_formats=None, out_dir: str | None = None):
        self.item = item  # FileItem
        self.task = task
        self.question = question
        self.dpi = dpi
        self.export_formats = export_formats  # None = just display the result
        self.out_dir = out_dir


class RecognitionWorker(QThread):
    jobStarted = Signal(object)          # Job
    ingestDone = Signal(object)          # IngestResult
    pageProgress = Signal(str, int, int) # path, pages done (1-based), total
    pageText = Signal(str, int, str)     # path, page index, recognized text
    jobFinished = Signal(object, object) # FileItem, Job
    fileExported = Signal(str, list)     # path, written files
    jobFailed = Signal(str, str)         # path, message
    queueCleared = Signal()              #ThreadPool очередь очищена

    def __init__(self, parent=None):
        super().__init__(parent)
        self._queue: deque[Job] = deque()
        self._cond = threading.Condition()
        self._stop = False

    # ------------------------------------------------------------ controls ----

    def submit(self, job: Job):
        with self._cond:
            self._stop = False
            self._queue.append(job)
            self._cond.notify_all()

    def stop_all(self):
        """Stop everything: clear pending jobs; the current page runs to its end."""
        with self._cond:
            self._stop = True
            self._queue.clear()
            self._cond.notify_all()

    def cancel_path(self, path: str):
        with self._cond:
            self._queue = deque(j for j in self._queue if j.item.path != path)

    # ------------------------------------------------------------ internal ----

    def _next_job(self) -> Job | None:
        with self._cond:
            while not self._queue and not self._stop and not self.isInterruptionRequested():
                self._cond.wait(0.1)
            if self._stop or self.isInterruptionRequested():
                return None
            return self._queue.popleft()

    def run(self):
        while not self.isInterruptionRequested():
            job = self._next_job()
            if job is None:
                self.queueCleared.emit()
                continue
            self.jobStarted.emit(job)
            try:
                self._run_job(job)
            except Exception as e:
                self.jobFailed.emit(job.item.path, format_exception(e) + "\n" + traceback.format_exc())

    def _run_job(self, job: Job):
        path = job.item.path
        try:
            result = ingest(path, dpi=job.dpi)
        except IngestError as e:
            self.jobFailed.emit(path, str(e))
            return
        except Exception as e:
            self.jobFailed.emit(path, format_exception(e))
            return
        self.ingestDone.emit(result)

        if result.kind == "text":
            texts = result.texts
        else:
            texts = self._recognize_page_texts(job, result, path)
        if texts is None:
            return  # stopped

        full = "\n\n".join(t.strip() for t in texts)
        if job.export_formats:
            text_obj = OcrText(source_path=path, full_text=full, pages=[])
            try:
                written = export_text(text_obj, job.out_dir, job.export_formats)
                self.fileExported.emit(path, written)
            except Exception as e:
                self.jobFailed.emit(path, "Export failed: " + format_exception(e))
        else:
            item = job.item
            if item.result is None:
                item.result = OcrText(source_path=path, full_text=full, pages=[])
            item.result.full_text = full
            self.jobFinished.emit(item, job)

    def _recognize_page_texts(self, job, result, path: str) -> list[str] | None:
        """OCR per page; returns None if stopped."""
        texts: list[str] = []
        total = result.page_count
        for i, image_path in enumerate(result.pages):
            if self._stop:
                self.jobFailed.emit(path, "Stopped by user.")
                return None
            texts.append(self._recognize_one(image_path, job, path, i))
            self.pageText.emit(path, i, texts[-1])
            self.pageProgress.emit(path, i + 1, total)
        return texts

    def _recognize_one(self, image_path: str, job: Job, path: str, page_index: int) -> str:
        while not (MODEL_READY.is_set() or MODEL_FAILED.is_set()
                   or self._stop or self.isInterruptionRequested()):
            time.sleep(0.2)
        if MODEL_FAILED.is_set():
            self.jobFailed.emit(path, "Model failed to load — recognition is not possible "
                                      "(see Journal).")
            return ""
        if self._stop or self.isInterruptionRequested():
            return ""
        try:
            engine = get_engine()
            return engine.recognize_image(image_path, task=job.task, question=job.question)
        except Exception as e:
            self.jobFailed.emit(path, f"Page {page_index + 1}: {format_exception(e)}\n{traceback.format_exc()}")
            return ""

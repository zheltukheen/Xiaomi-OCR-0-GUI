"""Главное окно приложения Xiaomi OCR (English UI)."""

from __future__ import annotations

import os

from PySide6.QtCore import Qt
from PySide6.QtGui import QAction, QKeySequence
from PySide6.QtWidgets import (
    QApplication, QFileDialog, QHBoxLayout, QLabel, QLineEdit, QMainWindow,
    QMessageBox, QProgressBar, QPushButton, QStackedWidget, QTabWidget,
    QVBoxLayout, QWidget,
)

from ..exporters import export_text
from ..file_item import FileItem
from ..ingest import IngestError, ingest
from ..model_manager import MODEL_READY, ModelLoaderWorker
from ..prompts import TASKS
from ..settings import AppSettings
from ..worker import Job, RecognitionWorker
from .dialogs import BatchOpenDialog, ExportDialog
from .document_view import DocumentView
from .log_window import LogWindow

OPEN_FILTER = (
    "All supported files (*.pdf *.png *.jpg *.jpeg *.bmp *.tif *.tiff *.webp *.jfif *.gif "
    "*.docx *.pptx *.odt *.rtf *.txt *.md *.markdown *.csv *.tsv *.json *.xml *.yaml *.yml "
    "*.ini *.log *.html *.htm);;All files (*)"
)


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Xiaomi OCR")
        self.resize(1280, 840)
        self.setAcceptDrops(True)

        self.settings = AppSettings()
        self.current_task = self.settings.task()
        self.current_device = self.settings.device()
        self.worker = RecognitionWorker(self)
        self.log_win: LogWindow | None = None
        self.batch_total = 0
        self.batch_done = 0

        self._build_menu()
        self._build_ui()
        # выставить сохранённые task/device как текущие значения (после _build_menu)
        self.question_edit.setText(str(self.settings.get("question", "")))

        # worker signals
        self.worker.jobStarted.connect(self._on_job_started)
        self.worker.ingestDone.connect(self._on_ingest_done)
        self.worker.pageProgress.connect(self._on_page_progress)
        self.worker.pageText.connect(self._on_page_text)
        self.worker.jobFinished.connect(self._on_job_finished)
        self.worker.fileExported.connect(self._on_file_exported)
        self.worker.jobFailed.connect(self._on_job_failed)
        self.worker.queueCleared.connect(self._on_queue_cleared)
        self.worker.start()

        # model loads immediately at startup
        self.loader = ModelLoaderWorker()
        self.loader.status.connect(self._on_model_status)
        self.loader.downloadProgress.connect(self._on_model_progress)
        self.loader.loadProgress.connect(self._on_model_status)
        self.loader.ready.connect(self._on_model_ready)
        self.loader.error.connect(self._on_model_error)
        self.loader.start()

    # ------------------------------------------------------------------ UI ----

    def _build_menu(self):
        mb = self.menuBar()

        m_file = mb.addMenu("&File")
        m_file.addAction("Open…", self._open_files, QKeySequence("Ctrl+O"))
        self.act_close_tab = m_file.addAction("Close Tab", self._close_current_tab, QKeySequence("Ctrl+W"))
        m_file.addSeparator()
        m_file.addAction("Export Current…", self._export_current, QKeySequence("Ctrl+E"))
        m_file.addSeparator()
        m_file.addAction("Exit", self.close, QKeySequence("Ctrl+Q"))

        m_settings = mb.addMenu("&Settings")
        m_task = m_settings.addMenu("Recognition task")
        for t in TASKS:
            act = QAction(t, self, checkable=True)
            act.setChecked(t == self.current_task)
            act.triggered.connect(lambda _=False, name=t: self._set_task(name))
            m_task.addAction(act)
        m_device = m_settings.addMenu("Device")
        for d in ("auto", "cuda", "mps", "cpu"):
            act = QAction(d, self, checkable=True)
            act.setChecked(d == self.current_device)
            act.triggered.connect(lambda _=False, name=d: self._set_device(name))
            m_device.addAction(act)
        m_dpi = m_settings.addMenu("PDF rendering DPI")
        for dpi in (100, 150, 200, 300):
            act = QAction(str(dpi), self, checkable=True)
            act.setChecked(dpi == self.settings.dpi())
            act.triggered.connect(lambda _=False, v=dpi: self._set_dpi(v))
            m_dpi.addAction(act)

        m_view = mb.addMenu("&View")
        m_view.addAction("Journal", self._show_journal, QKeySequence("Ctrl+J"))

        m_help = mb.addMenu("&Help")
        m_help.addAction("About", self._about)

    def _build_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        root = QVBoxLayout(central)

        self.welcome = QLabel(
            "<h3>Welcome</h3>"
            "<p>Open a file (File → Open… or drop it here) and recognition starts automatically.</p>"
            "<p>Model is loading — see the status bar below. First start downloads ~1.5&nbsp;GB "
            "of weights into the Hugging Face cache; after that everything runs offline.</p>"
        )
        self.welcome.setWordWrap(True)
        self.welcome.setAlignment(Qt.AlignTop)
        self.stack = QStackedWidget()
        self.stack.addWidget(self.welcome)          # index 0
        self.tabs = QTabWidget()
        self.tabs.setTabsClosable(True)
        self.tabs.setMovable(False)
        self.stack.addWidget(self.tabs)             # index 1
        if True:
            row = QWidget()
            form = QHBoxLayout(row)
            q_label = QLabel("VQA question (for “Ask a question (VQA)” task):")
            q_label.setToolTip("Used only when the task is “Ask a question (VQA)”")
            self.question_edit = QLineEdit()
            self.question_edit.setPlaceholderText("e.g. What is the total amount on the receipt?")
            form.addWidget(q_label)
            form.addWidget(self.question_edit, 1)
            self.stop_btn = QPushButton("Stop")
            self.stop_btn.setEnabled(False)
            self.stop_btn.clicked.connect(self._stop_all)
            form.addWidget(self.stop_btn)
            self.stack.addWidget(row)               # index 2 – then hidden
            row.hide()
        root.addWidget(self.stack, 1)

        self.model_status = QLabel("Model: starting…")
        self.model_progress = QProgressBar()
        self.model_progress.setFixedWidth(260)
        self.statusBar().addPermanentWidget(self.model_progress)
        self.statusBar().addPermanentWidget(self.model_status)
        self.statusBar().showMessage("Ready")

        self.tabs.currentChanged.connect(self._current_tab_changed)
        self.tabs.tabCloseRequested.connect(self._close_tab)

    def closeEvent(self, event):
        self._save_settings()
        if self.loader and self.loader.isRunning():
            self.loader.requestInterruption(); self.loader.wait(1500)
        if self.worker:
            self.worker.stop_all()
            self.worker.requestInterruption()
            self.worker.wait(8000)
        super().closeEvent(event)

    # ------------------------------------------------------------- helpers ----

    def _save_settings(self):
        self.settings.set("dpi", self.settings.dpi())
        self.settings.set("task", self.current_task)
        self.settings.set("device", self.current_device)
        self.settings.set("question", self.question_edit.text())

    def _log(self, msg: str):
        if self.log_win is None:
            self.log_win = LogWindow()
        self.log_win.append(msg)

    def _show_journal(self):
        if self.log_win is None:
            self.log_win = LogWindow()
            self.log_win.setAttribute(Qt.WA_DeleteOnClose)
        self.log_win.show()
        self.log_win.raise_()

    def _about(self):
        QMessageBox.information(
            self, "About",
            "Xiaomi OCR GUI\n\n"
            "Recognition is powered by the Xiaomi-OCR-0 model (0.8B, Apache-2.0)\n"
            "officially distributed via Hugging Face:\n"
            "huggingface.co/SeerRay-Lab/Xiaomi-OCR-0\n\n"
            "Weights are downloaded locally on first start (≈1.5 GB).\n"
            "Tables are recognized as OTSL and converted to HTML on export;\n"
            "formulas stay in LaTeX.",
        )

    # ------------------------------------------------------------- settings ----

    def _set_task(self, name: str):
        self.current_task = name
        self.settings.set("task", name)

    def _set_device(self, name: str):
        self.current_device = name
        self.settings.set("device", name)
        self.statusBar().showMessage(f"Device preference set to “{name}”; restart the app to apply.", 5000)

    def _set_dpi(self, dpi: int):
        self.settings.set("dpi", dpi)
        self.statusBar().showMessage(f"PDF rendering DPI set to {dpi}.", 5000)

    # ------------------------------------------------------------ open flow ----

    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()

    def dropEvent(self, event):
        paths = [u.toLocalFile() for u in event.mimeData().urls() if u.toLocalFile()]
        self._handle_paths([p for p in paths if os.path.isfile(p)])

    def _open_files(self):
        paths, _ = QFileDialog.getOpenFileNames(self, "Open files", "", OPEN_FILTER)
        self._handle_paths(paths)

    def _handle_paths(self, paths: list[str]):
        if not paths:
            return
        task = self.current_task
        question = self.question_edit.text()

        if len(paths) == 1:
            self._open_in_tab(paths[0], task, question)
            return

        dlg = BatchOpenDialog(len(paths), self)
        if dlg.exec() != BatchOpenDialog.Accepted:
            return
        if dlg.mode() == "tabs":
            for p in paths:
                self._open_in_tab(p, task, question)
        else:
            fmt = dlg.export_format()
            out_dir = dlg.out_dir()
            self.batch_total = len(paths)
            self.batch_done = 0
            for p in paths:
                item = FileItem(p)
                self._submit(item, task, question, export_formats=[fmt], out_dir=out_dir)
            self.statusBar().showMessage(f"Recognizing {self.batch_total} files for export as {fmt.upper()}…")

    def _open_in_tab(self, path: str, task: str, question: str):
        if self._find_view(path) is not None:
            self.tabs.setCurrentWidget(self._find_view(path))
            return
        item = FileItem(path)
        view = DocumentView(item)
        view.exportRequested.connect(self._export_item)
        self.tabs.addTab(view, os.path.basename(path))
        self.stack.setCurrentIndex(1)
        self._submit(item, task, question)

    def _submit(self, item: FileItem, task: str, question: str,
                export_formats=None, out_dir: str | None = None):
        job = Job(item, task, question, dpi=self.settings.dpi(),
                  export_formats=export_formats, out_dir=out_dir)
        item.job = job
        self.worker.submit(job)

    # ---------------------------------------------------------- worker slots ----

    def _on_job_started(self, job):
        view = self._find_view(job.item.path)
        if view:
            view.set_state("Preparing pages…")
        self.stop_btn.setEnabled(True)
        self.statusBar().showMessage(f"Processing: {os.path.basename(job.item.path)}")
        self._log(f"Started: {job.item.path}" + (f"  → export as {job.export_formats[0].upper()}" if job.export_formats else ""))

    def _on_ingest_done(self, result):
        view = self._find_view(result.path)
        total = result.page_count
        if view:
            view.set_ingested(total, result.kind)
            view.item.images = list(result.pages) if result.kind != "text" else None
        else:
            self.statusBar().showMessage(f"Recognizing {os.path.basename(result.path)}…")

    def _on_page_progress(self, path: str, done: int, total: int):
        view = self._find_view(path)
        msg = f"Recognizing page {done} / {total}"
        if view:
            view.set_state(msg)
        else:
            self.statusBar().showMessage(f"{os.path.basename(path)}: {msg}")
        if view is None:
            self._log(f"{path}: page {done}/{total}")

    def _on_page_text(self, path: str, index: int, text: str):
        view = self._find_view(path)
        if view:
            image_path = None
            if view.item.images and index < len(view.item.images):
                image_path = view.item.images[index]
            view.set_page(index, image_path, text)

    def _on_job_finished(self, item, job):
        view = self._find_view(item.path)
        if view:
            view.set_state("Recognized.")
            view.rebuild_from_result()
        self.statusBar().showMessage(f"Recognized: {os.path.basename(item.path)}")
        self._log(f"Finished: {item.path}")

    def _on_file_exported(self, path: str, written: list):
        self._log(f"Exported {path}: {', '.join(os.path.basename(w) for w in written)}")
        self.statusBar().showMessage(f"Exported {os.path.basename(path)} → {len(written)} file(s)")

    def _on_job_failed(self, path: str, message: str):
        self._log(f"ERROR ({os.path.basename(path) if path else '—'}): {message}")
        self.statusBar().showMessage("Error — see Journal", 5000)
        view = self._find_view(path)
        if view:
            view.set_state("Error (see Journal).")

    def _on_queue_cleared(self):
        self.stop_btn.setEnabled(False)
        self.statusBar().showMessage("Recognition stopped.")

    # ------------------------------------------------------------- stop flow ----

    def _stop_all(self):
        self.worker.stop_all()
        self.statusBar().showMessage("Stopping after the current page…")
        self._log("Stop requested: queue cleared; the running page finishes now.")
        for i in range(self.tabs.count()):
            v = self.tabs.widget(i)
            if isinstance(v, DocumentView) and v.item.state in ("recognizing", "queued"):
                v.item.state = "stopped"
                v.set_state("Stopped by user.")

    # ------------------------------------------------------------- export ----

    def _export_current(self):
        view = self.tabs.currentWidget()
        if isinstance(view, DocumentView):
            self._export_item(view.item)

    def _export_item(self, item: FileItem):
        if item.result is None or not item.result.full_text.strip():
            QMessageBox.information(self, "Nothing to export",
                                    "This document has not been recognized yet.")
            return
        default_dir = os.path.join(os.path.dirname(item.path) or ".", f"{item.result.base_name}_OCR")
        dlg = ExportDialog(default_dir=default_dir, parent=self)
        if dlg.exec() != ExportDialog.Accepted:
            return
        formats = dlg.selected_formats()
        if not formats:
            return
        out_dir = dlg.out_dir()
        try:
            written = export_text(item.result, out_dir, formats)
        except Exception as e:
            QMessageBox.critical(self, "Export failed", str(e))
            return
        self._log(f"Export of {item.path}: {len(written)} file(s)")
        QMessageBox.information(
            self, "Export",
            "Files were written:\n" + "\n".join(os.path.basename(w) for w in written),
        )

    # ------------------------------------------------------------- tab management ----

    def _close_current_tab(self):
        self._close_tab(self.tabs.currentIndex())

    def _close_tab(self, index: int):
        if index < 0:
            return
        view = self.tabs.widget(index)
        if isinstance(view, DocumentView):
            self.worker.cancel_path(view.item.path)
            view.item.state = "stopped"
        self.tabs.removeTab(index)
        if self.tabs.count() == 0:
            self.stack.setCurrentIndex(0)

    def _current_tab_changed(self, index: int):
        pass

    def _find_view(self, path: str) -> DocumentView | None:
        for i in range(self.tabs.count()):
            w = self.tabs.widget(i)
            if isinstance(w, DocumentView) and w.item.path == path:
                return w
        return None

    # ------------------------------------------------------------- model slots ----

    def _on_model_status(self, msg: str):
        self.model_status.setText(msg)
        self.model_progress.setRange(0, 0)
        self._log("Model: " + msg)

    def _on_model_progress(self, percent: int, msg: str):
        self.model_status.setText(msg)
        self.model_progress.setRange(0, 100)
        self.model_progress.setValue(percent)

    def _on_model_ready(self, device: str):
        self.model_status.setText(f"Model on device: {device}")
        self.model_progress.setRange(0, 100)
        self.model_progress.setValue(100)
        self.statusBar().showMessage("Model ready", 4000)
        self._log(f"Model ready on {device}")

    def _on_model_error(self, err: str):
        self.model_status.setText("Model load failed")
        self.model_progress.setRange(0, 100)
        self.model_progress.setValue(0)
        self.statusBar().showMessage("Model load failed — see Journal", 5000)
        self._log("Model load failed:\n" + err)
        QMessageBox.critical(self, "Model error", err)


def run_app():
    app = QApplication.instance() or QApplication([__import__("sys").argv[0]])
    app.setApplicationName("Xiaomi OCR")
    app.setApplicationDisplayName("Xiaomi OCR")
    win = MainWindow()
    win.show()
    return app.exec()

"""Document view: one tab per opened file.

Left pane — the original page image, right pane — the recognized text.
Panning/scrolling either pane moves the other one too (synced comparison).
"""

from __future__ import annotations

import os

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import (
    QCheckBox, QFileDialog, QHBoxLayout, QLabel, QPushButton, QScrollArea,
    QSlider, QSplitter, QTextBrowser, QVBoxLayout, QWidget,
)

from ..file_item import FileItem
from .html_helpers import PAGE_EMPTY_HTML, page_to_html


def _clamp_scrollbar(sb, value: int):
    if sb.maximum() <= 0:
        sb.setValue(0)
        return max(0, value)
    sb.setValue(max(0, min(int(value), sb.maximum())))
    return int(sb.value())


class DocumentView(QWidget):
    exportRequested = Signal(object)   # emits the FileItem
    settingsRequested = Signal()

    def __init__(self, item: FileItem, parent=None):
        super().__init__(parent)
        self.item = item
        self.page_count = 0
        self.show_markdown = False
        self._syncing = False

        layout = QVBoxLayout(self)
        layout.setContentsMargins(6, 6, 6, 0)

        header = QHBoxLayout()
        self.title_label = QLabel(os.path.basename(item.path))
        self.title_label.setStyleSheet("font-weight:600;")
        self.status_label = QLabel("")
        header.addWidget(self.title_label)
        header.addWidget(self.status_label, 1)

        self.md_btn = QPushButton("Raw")
        self.md_btn.setCheckable(True)
        self.md_btn.setToolTip("Show the raw model output (markdown)")
        self.sync_cb = QCheckBox("Pan sync")
        self.sync_cb.setChecked(True)
        self.sync_cb.setToolTip("Scroll the recognized text together with the image")
        self.export_btn = QPushButton("Export…")
        header.addSpacing(10)
        header.addWidget(self.sync_cb)
        header.addWidget(self.md_btn)
        header.addWidget(self.export_btn)
        layout.addLayout(header)

        self.splitter = QSplitter(Qt.Horizontal)
        layout.addWidget(self.splitter, 1)

        # ---------------------------------------------------------- left ----
        left = QWidget()
        ll = QVBoxLayout(left)
        ll.setContentsMargins(0, 0, 0, 0)
        self.image_scroll = QScrollArea()
        self.image_scroll.setWidgetResizable(True)
        self.image_label = QLabel("Original")
        self.image_label.setAlignment(Qt.AlignCenter)
        self.image_scroll.setWidget(self.image_label)
        ll.addWidget(self.image_scroll, 1)
        self.page_bar = QHBoxLayout()
        self.page_label = QLabel("Page 0 / 0")
        self.page_slider = QSlider(Qt.Horizontal)
        self.page_slider.setRange(0, 0)
        self.page_bar.addWidget(self.page_label)
        self.page_bar.addWidget(self.page_slider, 1)
        ll.addLayout(self.page_bar)
        self.splitter.addWidget(left)

        # --------------------------------------------------------- right ----
        right = QWidget()
        rl = QVBoxLayout(right)
        rl.setContentsMargins(0, 0, 0, 0)
        self.text_view = QTextBrowser()
        self.text_view.setOpenExternalLinks(True)
        self.text_view.setHtml(PAGE_EMPTY_HTML)
        rl.addWidget(self.text_view, 1)
        self.splitter.addWidget(right)
        self.splitter.setSizes([640, 640])

        # -------------------------------------------------------- wiring ----
        self.export_btn.clicked.connect(self._request_export)
        self.md_btn.toggled.connect(self._on_md_toggled)
        self.page_slider.valueChanged.connect(self._show_page)

        self.image_scroll.verticalScrollBar().valueChanged.connect(self._sync_text)
        self.text_view.verticalScrollBar().valueChanged.connect(self._sync_image)

    # -------------------------------------------------------------- state ----

    def set_state(self, text: str):
        self.status_label.setText(text)
        self.setWindowTitle(self.title_label.text())

    def set_ingested(self, page_count: int, kind: str):
        self.page_count = page_count
        self.page_slider.blockSignals(True)
        self.page_slider.setRange(0, max(page_count - 1, 0))
        self.page_slider.blockSignals(False)
        if kind != "ocr":
            self.image_label.setText("Text file — content is extracted directly,\nthere is no original page image to compare.")
        self._show_page(self.page_slider.value())

    def set_page(self, index: int, image_path: str | None, text: str):
        self.item.ensure_result()
        pages = self.item.result.pages
        while len(pages) <= index:
            pages.append({"index": len(pages), "image": None, "text": ""})
        pages[index]["image"] = image_path
        pages[index]["text"] = text
        if self.page_slider.value() == index:
            self._refresh()

    def rebuild_from_result(self):
        if self.item.result is None:
            return
        self.set_ingested(len(self.item.result.pages), "ocr")

    # ------------------------------------------------------------ display ----

    def _current(self) -> int:
        return min(self.page_slider.value(), max(self.page_count - 1, 0))

    def _show_page(self, index: int):
        self.page_label.setText(f"Page {index + 1} / {max(self.page_count, 1)}")
        self._refresh()

    def _refresh(self):
        index = self._current()
        result = self.item.result
        text = ""
        image_path = None
        if result is not None and index < len(result.pages):
            page = result.pages[index]
            text = page.get("text") or ""
            image_path = page.get("image")
        if image_path and os.path.isfile(image_path):
            self.image_label.setPixmap(QPixmap(image_path))
        elif result is not None and self.item.kind != "ocr":
            self.image_label.setPixmap(QPixmap())
            self.image_label.setText("Text file (no page image).")
        else:
            self.image_label.setPixmap(QPixmap())
        if self.show_markdown:
            self.text_view.setPlainText(text or "(waiting for recognition…)")
        else:
            self.text_view.setHtml(page_to_html(text))

    def _on_md_toggled(self, checked: bool):
        self.show_markdown = checked
        self.md_btn.setText("Raw" if self.show_markdown else "Rendered")
        self._refresh()

    def _request_export(self):
        self.exportRequested.emit(self.item)

    # --------------------------------------------------------------- sync ----

    def _sync_text(self, value):
        if not self.sync_cb.isChecked() or self._syncing:
            return
        self._syncing = True
        try:
            sb = self.text_view.verticalScrollBar()
            _clamp_scrollbar(sb, value)
        finally:
            self._syncing = False

    def _sync_image(self, value):
        if not self.sync_cb.isChecked() or self._syncing:
            return
        self._syncing = True
        try:
            sb = self.image_scroll.verticalScrollBar()
            _clamp_scrollbar(sb, value)
        finally:
            self._syncing = False

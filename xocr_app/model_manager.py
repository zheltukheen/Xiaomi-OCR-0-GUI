"""Model manager: loads Xiaomi-OCR-0 at application startup.

Weights are downloaded once from the official repo
https://huggingface.co/SeerRay-Lab/Xiaomi-OCR-0 (Apache-2.0) into the standard
Hugging Face cache. Download progress is computed from file sizes and polled
from the cache directory; loading progress is reported to the GUI.
"""

from __future__ import annotations

import os
import threading
import time
import traceback

from PySide6.QtCore import Signal, QThread

from . import MODEL_ID
from .model_engine import format_exception, get_engine

# Set once the model is ready for recognition requests.
MODEL_READY = threading.Event()
# Set if loading failed — the worker stops submitting recognition work.
MODEL_FAILED = threading.Event()


def _fmt_size(n: float) -> str:
    for unit in ("B", "KB", "MB", "GB"):
        if n < 1024 or unit == "GB":
            return f"{n:.0f} {unit}" if unit in ("B", "KB") else f"{n:.2f} {unit}"
        n /= 1024
    return f"{n:.2f} GB"


def _dir_size(path: str) -> int:
    total = 0
    for root, _dirs, files in os.walk(path):
        for f in files:
            try:
                total += os.path.getsize(os.path.join(root, f))
            except OSError:
                pass
    return total


class ModelLoaderWorker(QThread):
    status = Signal(str)
    downloadProgress = Signal(int, str)   # percent, message
    loadProgress = Signal(str)            # message while loading into memory
    ready = Signal(str)                   # device name
    error = Signal(str)

    def run(self):
        engine = get_engine()
        if engine.ready:
            MODEL_READY.set()
            self.ready.emit(f"{engine.device}")
            return
        try:
            self._download_and_load()
        except Exception as e:
            MODEL_FAILED.set()
            self.error.emit(format_exception(e) + "\n\n" + traceback.format_exc())

    def _download_and_load(self):
        engine = get_engine()
        from huggingface_hub import HfApi, constants, hf_hub_download
        from huggingface_hub.hf_api import RepoFile

        api = HfApi()
        entries = list(api.list_repo_tree(MODEL_ID, recursive=True))
        wanted = []
        for f in entries:
            if isinstance(f, RepoFile):
                size = (f.lfs.size if getattr(f, "lfs", None) else 0) or getattr(f, "size", 0) or 0
                wanted.append((f.path, size))
        total = sum(size for _p, size in wanted) or 0

        cache_dir = os.path.join(constants.HF_HUB_CACHE, "models--" + MODEL_ID.replace("/", "--"))
        blobs = os.path.join(cache_dir, "blobs")
        already = _dir_size(blobs)

        self.status.emit(f"Model: {len(wanted)} files, {_fmt_size(total)} total (cached: {_fmt_size(already)})")

        done = threading.Event()
        poll = threading.Thread(target=self._poll, args=(blobs, total, already, done), daemon=True)
        poll.start()

        for i, (path, _size) in enumerate(wanted, 1):
            if self.isInterruptionRequested():
                done.set()
                poll.join(timeout=1)
                return
            self.status.emit(f"Fetching {i}/{len(wanted)}: {path}")
            hf_hub_download(repo_id=MODEL_ID, filename=path)

        done.set()
        poll.join(timeout=2)
        self.downloadProgress.emit(100, "Download complete")

        self.loadProgress.emit("Loading model into memory...")
        device = engine.ensure_loaded("auto")
        MODEL_READY.set()
        self.ready.emit(device)

    def _poll(self, blobs: str, total: int, already: int, done: threading.Event):
        base = already
        last_pct = -1
        last_msg_time = 0.0
        while not done.is_set():
            size = _dir_size(blobs)
            downloaded = max(size, base)
            pct = int(min(99, (downloaded / total) * 100)) if total else 99
            msg = f"Downloading model: {_fmt_size(downloaded)} / {_fmt_size(total)}"
            now = time.time()
            if pct != last_pct and now - last_msg_time > 0.4:
                self.downloadProgress.emit(pct, msg)
                last_pct = pct
                last_msg_time = now
            if done.is_set():
                break
            time.sleep(0.4)

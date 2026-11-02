"""Model loading and inference for Xiaomi-OCR-0.

Weights are downloaded once from the official repository
https://huggingface.co/SeerRay-Lab/Xiaomi-OCR-0 (Apache-2.0) into the
standard Hugging Face cache (~/.cache/huggingface). The app itself is
lightweight — weights are not embedded.
"""

from __future__ import annotations

import threading
import traceback

from PySide6.QtCore import QObject, Signal

from . import MODEL_ID
from .prompts import prompt_for_task

_lock = threading.Lock()


class ModelError(RuntimeError):
    pass


def pick_device() -> tuple[str, str]:
    """Returns (device, description)."""
    import torch

    if torch.cuda.is_available():
        return "cuda", f"CUDA ({torch.cuda.get_device_name(0)})"
    if getattr(torch.backends, "mps", None) is not None and torch.backends.mps.is_available():
        return "mps", "Apple Metal (MPS)"
    return "cpu", "CPU"


def _dtype_for(device: str):
    import torch

    if device == "cpu":
        return torch.float32
    return torch.float16


class OcrEngine(QObject):
    """Singleton engine: loads the model lazily and keeps it in memory."""

    def __init__(self):
        super().__init__()
        self.model = None
        self.processor = None
        self.device = None

    @property
    def ready(self) -> bool:
        return self.model is not None

    def ensure_loaded(self, device: str = "auto") -> str:
        """Loads the model if not loaded yet. Returns the actual device."""
        with _lock:
            if self.ready:
                return self.device
            import torch
            from transformers import AutoModelForImageTextToText, AutoProcessor

            if device in ("auto", ""):
                resolved, _desc = pick_device()
            else:
                resolved = device

            self.model = AutoModelForImageTextToText.from_pretrained(
                MODEL_ID,
                dtype=_dtype_for(resolved),
                low_cpu_mem_usage=True,
            )
            self.processor = AutoProcessor.from_pretrained(MODEL_ID)
            if resolved == "mps":
                torch.mps.empty_cache()
            self.model = self.model.to(resolved).eval()
            self.device = resolved
            return resolved

    def recognize_image(self, image_path: str, task: str = "Full document parsing",
                        question: str = "", max_new_tokens: int = 4096) -> str:
        """Recognize one image; returns text/markdown. For VQA pass `question`."""
        import torch

        if not self.ready:
            raise ModelError("The model is not loaded yet")

        prompt = prompt_for_task(task, question)
        messages = [{
            "role": "user",
            "content": [
                {"type": "image", "url": image_path},
                {"type": "text", "text": prompt},
            ],
        }]

        inputs = self.processor.apply_chat_template(
            messages,
            tokenize=True,
            add_generation_prompt=True,
            return_dict=True,
            return_tensors="pt",
        )
        inputs = inputs.to(self.device)

        with torch.inference_mode():
            output = self.model.generate(**inputs, max_new_tokens=max_new_tokens, do_sample=False)
            new_tokens = output[:, inputs["input_ids"].shape[1]:]
            text = self.processor.batch_decode(new_tokens, skip_special_tokens=True)[0]
        text = text.strip()
        if not text:
            raise ModelError("The model returned an empty response")
        return text


_engine: OcrEngine | None = None


def get_engine() -> OcrEngine:
    global _engine
    if _engine is None:
        _engine = OcrEngine()
    return _engine


def format_exception(e: Exception) -> str:
    return "".join(traceback.format_exception_only(type(e), e)).strip()

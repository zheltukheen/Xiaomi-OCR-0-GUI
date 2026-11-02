#!/usr/bin/env python3
"""Application entry point for Xiaomi OCR.

Checks dependencies and launches the GUI.
On first launch the Xiaomi-OCR-0 model (~1.5 GB) is downloaded once from
the official Hugging Face repository into the standard cache.
"""

import sys

MIN_PY = (3, 10)


def check_python():
    if sys.version_info < MIN_PY:
        print(f"Python {MIN_PY[0]}.{MIN_PY[1]}+ is required (found {sys.version.split()[0]}).")
        sys.exit(1)


def check_deps():
    missing = []
    for _name, mod in (("PySide6", "PySide6"), ("torch", "torch"), ("transformers", "transformers")):
        try:
            __import__(mod)
        except ImportError:
            missing.append(_name)
    if missing:
        print("Missing dependencies. Install them and run again:\n")
        print("    pip install -r requirements.txt\n")
        print(f"(missing: {', '.join(missing)})")
        sys.exit(1)


def main():
    check_python()
    check_deps()

    def qt_excepthook(etype, value, tb):
        import traceback
        print("".join(traceback.format_exception(etype, value, tb)), file=sys.stderr)

    sys.excepthook = qt_excepthook

    from xocr_app.ui.main_window import run_app
    sys.exit(run_app())


if __name__ == "__main__":
    main()

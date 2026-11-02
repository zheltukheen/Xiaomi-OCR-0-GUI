#!/usr/bin/env python3
"""Точка входа приложения Xiaomi OCR.

Проверяет зависимости и запускает графический интерфейс.
Первый запуск скачивает модель Xiaomi-OCR-0 (~1.5 ГБ) с официального
репозитория Hugging Face в стандартный кеш.
"""

import sys

MIN_PY = (3, 10)


def check_python():
    if sys.version_info < MIN_PY:
        print(f"Нужен Python {MIN_PY[0]}.{MIN_PY[1]}+ (у вас {sys.version.split()[0]}).")
        sys.exit(1)


def check_deps():
    missing = []
    for _name, mod in (("PySide6", "PySide6"), ("torch", "torch"), ("transformers", "transformers")):
        try:
            __import__(mod)
        except ImportError:
            missing.append(_name)
    if missing:
        print("Не хватает зависимостей. Установите их и повторите запуск:\n")
        print("    pip install -r requirements.txt\n")
        print(f"(отсутствуют: {', '.join(missing)})")
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

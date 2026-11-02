#!/usr/bin/env bash
# Установка зависимостей и запуск Xiaomi OCR (macOS / Linux)
set -e
cd "$(dirname "$0")"

# Модель по официальному README работает связкой transformers 5.17 + torch 2.14,
# которая протестирована для Python 3.10–3.13. Выберем подходящую версию Python.
PY=python3
for cand in python3.13 python3.12 python3.11 python3.10; do
  if command -v "$cand" >/dev/null 2>&1; then PY="$cand"; break; fi
done
echo "Использую интерпретатор: $PY ($($PY --version 2>&1))"

if [ ! -d .venv ]; then
  echo "Создаю виртуальное окружение..."
  "$PY" -m venv .venv
fi

source .venv/bin/activate

echo "Обновляю pip и ставлю зависимости (около 2 ГБ, скачивается один раз)..."
python -m pip install --upgrade pip >/dev/null
pip install -r requirements.txt

echo
echo "Запускаю приложение..."
python run.py "$@"

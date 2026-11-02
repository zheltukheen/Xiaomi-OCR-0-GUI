#!/usr/bin/env bash
# Install dependencies and launch Xiaomi OCR (macOS / Linux).
set -e
cd "$(dirname "$0")"

# The official model README verifies transformers 5.17 + torch 2.14 on Python 3.10–3.13.
PY=python3
for cand in python3.13 python3.12 python3.11 python3.10; do
  if command -v "$cand" >/dev/null 2>&1; then PY="$cand"; break; fi
done
echo "Using interpreter: $PY ($($PY --version 2>&1))"

if [ ! -d .venv ]; then
  echo "Creating virtual environment..."
  "$PY" -m venv .venv
fi

source .venv/bin/activate

echo "Upgrading pip and installing dependencies (about 2 GB, downloaded once)..."
python -m pip install --upgrade pip >/dev/null
pip install -r requirements.txt

echo
echo "Launching the application..."
python run.py "$@"

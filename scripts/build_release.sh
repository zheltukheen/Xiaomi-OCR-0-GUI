#!/usr/bin/env bash
# Build a standalone app bundle for the CURRENT platform.
# Cross-platform builds are done by GitHub Actions (.github/workflows/build.yml).
set -e
cd "$(dirname "$0")/.."

echo "Platform: $(uname -s)"

if [ ! -d .venv ]; then
  echo "Creating venv..."
  python3 -m venv .venv || ${PYTHON:-python} -m venv .venv
  ./.venv/bin/pip install --upgrade pip
fi

if command -v uv >/dev/null 2>&1; then
  uv pip install -r requirements.txt pyinstaller
else
  ./.venv/bin/pip install -r requirements.txt pyinstaller
fi

NAME="XiaomiOCR"
rm -rf build dist/${NAME}*

if [ "$(uname -s)" = "Darwin" ]; then
  ./.venv/bin/pyinstaller run.py \
    --name "${NAME}" \
    --windowed --onedir \
    --collect-all pymupdf \
    --collect-all odfpy \
    --collect-all ebooklib \
    --collect-all striprtf \
    --collect-data transformers \
    --noconsole
else
  ./.venv/bin/pyinstaller run.py \
    --name "${NAME}" \
    --windowed --onedir \
    --collect-all pymupdf \
    --collect-all odfpy \
    --collect-all ebooklib \
    --collect-all striprtf \
    --collect-data transformers
fi

# Package into a zip for distribution
if [ "$(uname -s)" = "Darwin" ]; then
  (cd dist && zip -q -r "${NAME}-macos.zip" "${NAME}.app" "${NAME}" 2>/dev/null || zip -q -r "${NAME}-macos.zip" "${NAME}")
else
  (cd dist && zip -q -r "${NAME}-linux.zip" "${NAME}")
fi

ls -la dist
echo "Done."

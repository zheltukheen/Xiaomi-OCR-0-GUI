#!/usr/bin/env bash
# Build a standalone app bundle for the CURRENT platform:
#   macOS  -> dist/XiaomiOCR.app (+ XiaomiOCR-macos.zip with the .app inside)
#   Linux  -> dist/XiaomiOCR.AppImage (+ XiaomiOCR-linux.AppImage file)
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
python scripts/gen_icon.py

COMMON="--collect-all pymupdf --collect-all odfpy --collect-all ebooklib --collect-all striprtf"

if [ "$(uname -s)" = "Darwin" ]; then
  iconutil -c icns icons/icon.iconset -o icons/icon.icns
  ./.venv/bin/pyinstaller run.py --name "${NAME}" --onedir --windowed \
    --icon icons/icon.icns $COMMON
  (cd dist && zip -q -r "${NAME}-macos.zip" "${NAME}.app")
else
  ./.venv/bin/pyinstaller run.py --name "${NAME}" --onedir --windowed $COMMON
  mkdir -p AppDir/usr/bin AppDir/usr/share/icons/hicolor/256x256/apps
  cp -r dist/"${NAME}" AppDir/usr/bin/
  chmod +x AppDir/usr/bin/"${NAME}"/"${NAME}"
  cat > AppDir/AppRun <<EOF
#!/bin/bash
SELF="\$(readlink -f "\$0")"
HERE="\${SELF%/*}"
exec "\$HERE/usr/bin/${NAME}/${NAME}" "\$@"
EOF
  chmod a+rx AppDir/AppRun
  cp icons/icon.png AppDir/usr/share/icons/hicolor/256x256/apps/xocr.png
  cp icons/icon.png AppDir/.DirIcon
  cp icons/icon.png AppDir/xocr.png
  cat > AppDir/xocr.desktop <<EOF
[Desktop Entry]
Type=Application
Name=${NAME}
Comment=Offline OCR powered by Xiaomi-OCR-0
Exec=${NAME}
Icon=xocr
Categories=Office;
Terminal=false
EOF
  if command -v appimagetool >/dev/null 2>&1; then
    appimagetool AppDir dist/"${NAME}"-linux.AppImage
  else
    curl -L -o appimagetool https://github.com/AppImage/appimagetool/releases/download/continuous/appimagetool-x86_64.AppImage
    chmod +x appimagetool
    ./appimagetool --appimage-extract-and-run AppDir dist/"${NAME}"-linux.AppImage
  fi
fi

ls -la dist
echo "Done."

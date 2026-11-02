@echo off
rem Build the standalone app bundle for Windows.
rem Cross-platform builds are done by GitHub Actions (.github\workflows\build.yml).
cd /d "%~dp0\.."

if not exist .venv (
  echo Creating venv...
  python -m venv .venv
)
call .venv\Scripts\activate.bat
python -m pip install --upgrade pip
pip install -r requirements.txt pyinstaller

set NAME=XiaomiOCR
if exist build rmdir /s /q build
if exist dist\%NAME% rmdir /s /q dist\%NAME%

pyinstaller run.py ^
  --name "%NAME%" ^
  --windowed --onedir ^
  --collect-all pymupdf ^
  --collect-all odfpy ^
  --collect-all ebooklib ^
  --collect-all striprtf

powershell -Command "Compress-Archive -Path 'dist\%NAME%' -DestinationPath 'dist\XiaomiOCR-windows.zip' -Force"
dir dist
echo Done.

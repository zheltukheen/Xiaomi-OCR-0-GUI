@echo off
rem Build the standalone Windows bundle: a single double-clickable XiaomiOCR.exe.
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
if exist dist rmdir /s /q dist
python scripts\gen_icon.py

pyinstaller run.py ^
  --name "%NAME%" ^
  --onefile --windowed ^
  --icon icons\icon.ico ^
  --collect-all pymupdf ^
  --collect-all odfpy ^
  --collect-all ebooklib ^
  --collect-all striprtf

if not exist dist mkdir dist
powershell -Command "Compress-Archive -Path 'dist\%NAME%.exe' -DestinationPath 'dist\%NAME%-windows.zip' -Force"
dir dist
echo Done.

@echo off
rem Установка зависимостей и запуск Xiaomi OCR (Windows)
cd /d "%~dp0"

if not exist .venv (
  echo Создаю виртуальное окружение...
  python -m venv .venv
)

call .venv\Scripts\activate.bat

echo Устанавливаю зависимости...
python -m pip install --upgrade pip
pip install -r requirements.txt

echo Запускаю приложение...
python run.py %*

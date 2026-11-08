@echo off
cd /d "%~dp0"

if not exist .venv (
    echo Creating virtual environment...
    python -m venv .venv
)
call .venv\Scripts\activate

echo Installing packages...
python -m pip install -r requirements.txt

echo Building exe (this takes 1-3 minutes)...
pyinstaller --onefile --noconsole --clean --name DIPLabStudio --icon icon.ico --add-data "web;web" --add-data ".venv\Lib\site-packages\eel\eel.js;eel" main.py

echo.
if exist dist\DIPLabStudio.exe (
    echo SUCCESS: your app is at %cd%\dist\DIPLabStudio.exe
    explorer dist
) else (
    echo Build failed. Scroll up to read the error.
)
pause

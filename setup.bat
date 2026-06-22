@echo off
REM Creates an isolated virtual environment and installs all dependencies.
cd /d "%~dp0"

if not exist ".venv" (
    echo Creating virtual environment (.venv)...
    python -m venv .venv
)

echo Upgrading pip...
.venv\Scripts\python.exe -m pip install --upgrade pip

echo Installing dependencies...
.venv\Scripts\python.exe -m pip install -r requirements.txt

echo.
echo Setup complete. Launch the app with: run.bat
pause

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

REM --- ICU compatibility fix ---------------------------------------------
REM On a conda-forge based Python, the conda base dir is on the DLL search
REM path and ships an ancient icuuc.dll (ICU v58) that shadows the system
REM one. PySide6's Qt6Core.dll imports icuuc.dll unversioned and expects
REM Windows' system ICU, so it fails to load (WinError 127). Dropping the
REM system icuuc.dll next to Qt6Core.dll makes it resolve first.
echo Applying ICU compatibility fix...
for /f "delims=" %%i in ('.venv\Scripts\python.exe -c "import PySide6,os;print(os.path.dirname(PySide6.__file__))"') do set "PYSIDE_DIR=%%i"
if defined PYSIDE_DIR (
    if not exist "%PYSIDE_DIR%\icuuc.dll" (
        if exist "%WINDIR%\System32\icuuc.dll" (
            copy /Y "%WINDIR%\System32\icuuc.dll" "%PYSIDE_DIR%\icuuc.dll" >nul
            echo   Copied system icuuc.dll into PySide6.
        ) else (
            echo   WARNING: %WINDIR%\System32\icuuc.dll not found; skipping.
        )
    )
)

echo.
echo Setup complete. Launch the app with: run.bat
pause

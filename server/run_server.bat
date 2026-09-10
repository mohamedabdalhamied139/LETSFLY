@echo off
setlocal EnableExtensions
cd /d "%~dp0.."

if not exist ".venv\Scripts\python.exe" (
    echo Creating Python virtual environment...
    python -m venv .venv
    if errorlevel 1 (
        echo ERROR: Failed to create Python virtual environment.
        exit /b 1
    )
    set "NEEDS_INSTALL=1"
) else (
    set "NEEDS_INSTALL=0"
)

if "%NEEDS_INSTALL%"=="0" (
    ".venv\Scripts\python.exe" -m pip check >nul 2>&1
    if errorlevel 1 set "NEEDS_INSTALL=1"
)

if "%NEEDS_INSTALL%"=="1" (
    echo Installing/verifying server dependencies...
    ".venv\Scripts\python.exe" -m pip install -r requirements.txt
    if errorlevel 1 exit /b 1
    ".venv\Scripts\python.exe" -m pip check
    if errorlevel 1 exit /b 1
) else (
    echo Server environment is ready. Skipping dependency installation.
)

set "PYTHONPATH=%CD%"
".venv\Scripts\python.exe" server\run_server.py
exit /b %ERRORLEVEL%

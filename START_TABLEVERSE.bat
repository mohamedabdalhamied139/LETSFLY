@echo off
setlocal EnableExtensions EnableDelayedExpansion
set "ROOT=%~dp0"
cd /d "%ROOT%"

title TableVerse Platform v2.0
chcp 65001 >nul
if not exist "logs" mkdir "logs" >nul 2>&1

echo ========================================================
echo         Starting TableVerse Gaming Platform v2.0
echo ========================================================
echo.

echo [1/3] Checking previous TableVerse processes...
taskkill /f /im TableVerse.exe >nul 2>&1
taskkill /f /im TableVerse_Client.exe >nul 2>&1
powershell -NoProfile -ExecutionPolicy Bypass -Command "$p=Get-CimInstance Win32_Process -ErrorAction SilentlyContinue | Where-Object { $_.CommandLine -match 'server[\\/]run_server\.py' -or $_.CommandLine -match 'server[\\/]app[\\/]main' }; $p | ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }" >nul 2>&1

echo [2/3] Checking Python environment...
set "BASE_PYTHON="
py -3 -c "import sys; print(sys.executable)" >"%TEMP%\tableverse_python_path.txt" 2>nul
if not errorlevel 1 set /p BASE_PYTHON=<"%TEMP%\tableverse_python_path.txt"
if not defined BASE_PYTHON (
    python -c "import sys; print(sys.executable)" >"%TEMP%\tableverse_python_path.txt" 2>nul
    if not errorlevel 1 set /p BASE_PYTHON=<"%TEMP%\tableverse_python_path.txt"
)
del "%TEMP%\tableverse_python_path.txt" >nul 2>&1
if not defined BASE_PYTHON (
    echo ERROR: Python 3 was not found in PATH.
    echo Install Python 3.10 or newer and run START_TABLEVERSE.bat again.
    pause
    exit /b 1
)
echo Using Python: !BASE_PYTHON!

if not exist ".venv\Scripts\python.exe" (
    echo [2a] Creating Python virtual environment...
    echo This can take a minute on the first run.
    "!BASE_PYTHON!" -m venv .venv
    if errorlevel 1 (
        echo ERROR: Failed to create Python virtual environment.
        pause
        exit /b 1
    )
    echo [2a] Virtual environment created successfully.
)
if not exist ".venv\Scripts\python.exe" (
    echo ERROR: The virtual environment was not created correctly.
    pause
    exit /b 1
)

echo [2b] Checking dependency fingerprint...
set "REQ_HASH="
for /f "delims=" %%H in ('".venv\Scripts\python.exe" -c "import hashlib; print(hashlib.sha256(open(r'requirements.txt','rb').read()).hexdigest())" 2^>nul') do set "REQ_HASH=%%H"
set "NEEDS_INSTALL=0"
if not defined REQ_HASH set "NEEDS_INSTALL=1"
if not exist ".venv\.tableverse_requirements.sha256" set "NEEDS_INSTALL=1"
if "!NEEDS_INSTALL!"=="0" set /p SAVED_HASH=<".venv\.tableverse_requirements.sha256"
if "!NEEDS_INSTALL!"=="0" if /I not "!REQ_HASH!"=="!SAVED_HASH!" set "NEEDS_INSTALL=1"

echo [2c] Verifying required Python packages...
".venv\Scripts\python.exe" -c "import PySide6, httpx, websocket, sqlalchemy, bcrypt, fastapi, uvicorn" >nul 2>&1
if errorlevel 1 set "NEEDS_INSTALL=1"

if "!NEEDS_INSTALL!"=="1" (
    echo [2d] Installing/verifying required dependencies...
    ".venv\Scripts\python.exe" -m pip install --disable-pip-version-check -r requirements.txt
    if errorlevel 1 (
        echo.
        echo ERROR: Failed to install required dependencies.
        echo Check your Internet connection and Python installation, then try again.
        pause
        exit /b 1
    )
    echo [2e] Running dependency consistency check...
    ".venv\Scripts\python.exe" -m pip check
    if errorlevel 1 (
        echo ERROR: Dependency verification failed after installation.
        pause
        exit /b 1
    )
    if defined REQ_HASH echo !REQ_HASH!>.venv\.tableverse_requirements.sha256
) else (
    echo Python environment is ready. Dependencies are current.
)

echo [3/3] Launching TableVerse...
".venv\Scripts\python.exe" -u client\main.py
set "EXIT_CODE=%ERRORLEVEL%"
echo.
if not "%EXIT_CODE%"=="0" (
    echo TableVerse exited with code %EXIT_CODE%.
    echo Check logs\client_crash.log and logs\client_faulthandler.log if present.
) else (
    echo TableVerse closed normally.
)
exit /b %EXIT_CODE%

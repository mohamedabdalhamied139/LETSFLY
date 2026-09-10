@echo off
setlocal EnableExtensions
set "ROOT=%~dp0"
cd /d "%ROOT%"

title Let's Fly Platform v2.0
chcp 65001 >nul

echo ========================================================
echo         Starting Let's Fly Gaming Platform v2.0
echo ========================================================
echo.

:: 1. Stop only stale Let's Fly processes from this installation.
echo [1/3] Checking previous Let's Fly processes...
taskkill /f /im LetsFly.exe >nul 2>&1
taskkill /f /im LetsFly_Client.exe >nul 2>&1
powershell -NoProfile -ExecutionPolicy Bypass -Command "$p=Get-CimInstance Win32_Process -ErrorAction SilentlyContinue | Where-Object { $_.CommandLine -match 'server[\\/]run_server\.py' -or $_.CommandLine -match 'server[\\/]app[\\/]main' }; $p | ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }" >nul 2>&1

:: 2. Create/check the isolated environment. Revalidate when requirements change.
echo [2/3] Checking Python environment...
if not exist ".venv\Scripts\python.exe" (
    echo Creating Python virtual environment...
    where python >nul 2>&1
    if errorlevel 1 (
        echo ERROR: Python was not found in PATH.
        echo Install Python 3.10+ and run START_LETSFLY.bat again.
        pause
        exit /b 1
    )
    python -m venv .venv
    if errorlevel 1 (
        echo ERROR: Failed to create Python virtual environment.
        pause
        exit /b 1
    )
    set "NEEDS_INSTALL=1"
) else (
    set "NEEDS_INSTALL=0"
)

:: pip check alone cannot detect a newly-added package that is completely absent.
:: Keep a requirements fingerprint so dependency changes force one installation.
if "%NEEDS_INSTALL%"=="0" (
    for /f "delims=" %%H in ('powershell -NoProfile -Command "(Get-FileHash -Algorithm SHA256 'requirements.txt').Hash"') do set "REQ_HASH=%%H"
    if not exist ".venv\.letsfly_requirements.sha256" set "NEEDS_INSTALL=1"
    if "%NEEDS_INSTALL%"=="0" set /p SAVED_HASH=<".venv\.letsfly_requirements.sha256"
    if "%NEEDS_INSTALL%"=="0" if /I not "%REQ_HASH%"=="%SAVED_HASH%" set "NEEDS_INSTALL=1"
)

:: Also verify the packages required to start the desktop client. This catches
:: environments created before a new dependency was added to requirements.txt.
if "%NEEDS_INSTALL%"=="0" (
    ".venv\Scripts\python.exe" -c "import PySide6, httpx, websocket, sqlalchemy, bcrypt" >nul 2>&1
    if errorlevel 1 set "NEEDS_INSTALL=1"
)

if "%NEEDS_INSTALL%"=="1" (
    echo Installing/verifying required dependencies...
    ".venv\Scripts\python.exe" -m pip install -r requirements.txt
    if errorlevel 1 (
        echo.
        echo ERROR: Failed to install required dependencies.
        echo Check your Internet connection and try again.
        pause
        exit /b 1
    )
    ".venv\Scripts\python.exe" -m pip check
    if errorlevel 1 (
        echo ERROR: Dependency verification failed after installation.
        pause
        exit /b 1
    )
    for /f "delims=" %%H in ('powershell -NoProfile -Command "(Get-FileHash -Algorithm SHA256 'requirements.txt').Hash"') do echo %%H>".venv\.letsfly_requirements.sha256"
) else (
    echo Python environment is ready. Dependencies are current.
)

:: 3. client/main.py owns the embedded server lifecycle. Do not start a second
:: standalone server here; this prevents duplicate server processes and races.
echo [3/3] Launching Let's Fly...
".venv\Scripts\python.exe" client\main.py
set "EXIT_CODE=%ERRORLEVEL%"

echo.
if not "%EXIT_CODE%"=="0" (
    echo Let's Fly exited with code %EXIT_CODE%.
) else (
    echo Let's Fly closed normally.
)
exit /b %EXIT_CODE%

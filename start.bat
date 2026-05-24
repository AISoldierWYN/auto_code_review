@echo off
REM ===================================================================
REM  AI Code Review -- one-click launcher.
REM
REM  - Default port: 8765 (override: start.bat 9000)
REM  - If something is already listening on the port, the launcher kills
REM    it before starting the server.
REM  - Requires that .venv exists (see first-time setup hint below).
REM ===================================================================

setlocal

if "%~1"=="" (
    set PORT=8765
) else (
    set PORT=%~1
)

set PROJECT_ROOT=%~dp0
set VENV_PYTHON=%PROJECT_ROOT%.venv\Scripts\python.exe

if not exist "%VENV_PYTHON%" (
    echo [kit] ERROR: Python venv not found at:
    echo        %VENV_PYTHON%
    echo.
    echo [kit] First-time setup:
    echo        py -3.12 -m venv .venv
    echo        .venv\Scripts\python.exe -m pip install -e .[dev]
    exit /b 1
)

if not exist "%PROJECT_ROOT%.env" (
    echo [kit] WARNING: .env not found at %PROJECT_ROOT%.env
    echo        The server will fail without ANTHROPIC_BASE_URL / ANTHROPIC_AUTH_TOKEN.
    echo        Copy .env.example to .env and fill in values.
    echo.
)

echo [kit] checking port %PORT% ...

set FOUND=0
for /f "tokens=5" %%a in ('netstat -ano ^| findstr ":%PORT% " ^| findstr "LISTENING"') do (
    if not "%%a"=="0" (
        echo [kit] killing PID %%a currently holding port %PORT%
        taskkill /F /PID %%a >nul 2>&1
        set FOUND=1
    )
)

if "%FOUND%"=="1" (
    timeout /t 1 /nobreak >nul
)

echo [kit] starting server at http://127.0.0.1:%PORT%/
echo [kit] open the URL in your browser; press Ctrl-C in this window to stop.
echo.

"%VENV_PYTHON%" "%PROJECT_ROOT%scripts\serve.py" --port %PORT%

endlocal

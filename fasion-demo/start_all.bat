@echo off
REM ============================================================
REM  Apparel Demo - Start All Servers (single window)
REM  Runs Flask App, PayPal MCP Server, and A2UI Protocol Server
REM  together in ONE cmd window using run_all_servers.py.
REM ============================================================

setlocal
cd /d "%~dp0"

echo ============================================================
echo   Apparel Demo - Starting All Servers (single window)
echo ============================================================
echo.

REM --- Free up ports if already in use ---
echo Cleaning up any processes on ports 5000, 8010, 8020...
for /f "tokens=5" %%a in ('netstat -aon ^| find ":5000" ^| find "LISTENING"') do taskkill /F /PID %%a >nul 2>&1
for /f "tokens=5" %%a in ('netstat -aon ^| find ":8010" ^| find "LISTENING"') do taskkill /F /PID %%a >nul 2>&1
for /f "tokens=5" %%a in ('netstat -aon ^| find ":8020" ^| find "LISTENING"') do taskkill /F /PID %%a >nul 2>&1
echo Done.
echo.

REM --- Choose python: prefer venv if present ---
set "PYTHON_CMD=python"
if exist "venv\Scripts\python.exe" (
    set "PYTHON_CMD=venv\Scripts\python.exe"
    echo Using virtual environment: venv\Scripts\python.exe
) else (
    echo Using system Python.
)
echo.

echo Starting all servers in this window...
echo   Flask App:            http://localhost:5000
echo   PayPal MCP Server:    http://localhost:8010
echo   A2UI Protocol Server: http://localhost:8020
echo   A2UI WebSocket:       ws://localhost:8020/ws/{session_id}
echo.
echo Press Ctrl+C to stop all servers.
echo ============================================================
echo.

REM --- Launch the unified Python runner (all 3 in one process) ---
%PYTHON_CMD% run_all_servers.py

echo.
echo ============================================================
echo   All servers stopped.
echo ============================================================
echo.
pause
endlocal

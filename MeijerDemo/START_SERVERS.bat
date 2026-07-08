@echo off
REM ===============================================
REM AI Shopping Assistant - Server Startup Script
REM ===============================================
echo.
echo ============================================
echo  AI Shopping Assistant - Starting Servers
echo ============================================
echo.
echo This script will start both:
echo   1. Flask App (Main Application)
echo   2. PayPal MCP Server (Payment Gateway)
echo.
echo Press Ctrl+C to stop both servers
echo.
echo ============================================
echo.

REM Activate virtual environment if it exists
if exist "venv\Scripts\activate.bat" (
    echo Activating virtual environment...
    call venv\Scripts\activate.bat
    echo.
)

REM Run the dual server launcher
echo Starting servers...
python run_both_servers.py

REM If the script exits, pause so user can see any errors
echo.
echo ============================================
echo Servers stopped.
echo ============================================
pause

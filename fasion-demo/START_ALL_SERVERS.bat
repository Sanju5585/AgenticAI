@echo off
echo ========================================
echo  Starting All Servers (Unified Launcher)
echo ========================================
echo.

REM Kill any existing processes on the ports
echo Checking for existing processes...
for /f "tokens=5" %%a in ('netstat -aon ^| find ":5000" ^| find "LISTENING"') do taskkill /F /PID %%a 2>NUL
for /f "tokens=5" %%a in ('netstat -aon ^| find ":8010" ^| find "LISTENING"') do taskkill /F /PID %%a 2>NUL
for /f "tokens=5" %%a in ('netstat -aon ^| find ":8020" ^| find "LISTENING"') do taskkill /F /PID %%a 2>NUL

echo.
echo ========================================
echo  Starting All Servers...
echo ========================================
echo.
echo Using unified launcher: run_all_servers.py
echo This will start:
echo  - Flask App (port 5000)
echo  - PayPal MCP Server (port 8010)
echo  - A2UI Protocol Server (port 8020)
echo.

REM Activate virtual environment if it exists
if exist "venv\Scripts\activate.bat" (
    call venv\Scripts\activate.bat
)

REM Start all servers using the unified launcher
python run_all_servers.py
echo.
echo Stopping all servers...
for /f "tokens=5" %%a in ('netstat -aon ^| find ":5000" ^| find "LISTENING"') do taskkill /F /PID %%a 2>NUL
for /f "tokens=5" %%a in ('netstat -aon ^| find ":8010" ^| find "LISTENING"') do taskkill /F /PID %%a 2>NUL
for /f "tokens=5" %%a in ('netstat -aon ^| find ":8020" ^| find "LISTENING"') do taskkill /F /PID %%a 2>NUL

echo All servers stopped.
echo.
pause

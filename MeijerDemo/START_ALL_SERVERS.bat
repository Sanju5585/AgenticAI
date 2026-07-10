@echo off
echo ========================================
echo  Starting All Servers with A2UI Protocol
echo ========================================
echo.

REM Set workspace directory
set WORKSPACE_DIR=%~dp0
cd /d "%WORKSPACE_DIR%"

REM Set virtual environment Python path
set VENV_PYTHON=%WORKSPACE_DIR%.venv\Scripts\python.exe
set VENV_UVICORN=%WORKSPACE_DIR%.venv\Scripts\uvicorn.exe

REM Verify virtual environment exists
if not exist "%VENV_PYTHON%" (
    echo ERROR: Virtual environment not found at .venv\Scripts\python.exe
    echo Please create the virtual environment first: python -m venv .venv
    echo Then install dependencies: .venv\Scripts\pip install -r requirements.txt
    pause
    exit /b 1
)

REM Detect local IP for display
for /f "tokens=4" %%a in ('route print 0.0.0.0 ^| findstr "0.0.0.0" ^| findstr /v "127." ^| findstr /v "On-link"') do set LOCAL_IP=%%a

REM Kill any existing processes on the ports
echo Checking for existing processes on ports 5000, 8010, 8020...
for /f "tokens=5" %%a in ('netstat -aon ^| find ":5000" ^| find "LISTENING"') do taskkill /F /PID %%a 2>NUL
for /f "tokens=5" %%a in ('netstat -aon ^| find ":8010" ^| find "LISTENING"') do taskkill /F /PID %%a 2>NUL
for /f "tokens=5" %%a in ('netstat -aon ^| find ":8020" ^| find "LISTENING"') do taskkill /F /PID %%a 2>NUL
timeout /t 2 /nobreak >NUL

echo.
echo ========================================
echo  Starting Servers...
echo ========================================
echo.

REM Start PayPal MCP Server (FastAPI - requires uvicorn)
echo [1/3] Starting PayPal MCP Server on port 8010...
start "PayPal MCP Server" cmd /k "cd /d "%WORKSPACE_DIR%" && set PAYPAL_MCP_PORT=8010 && set PAYPAL_MCP_BIND_HOST=0.0.0.0 && "%VENV_UVICORN%" Paypal_MCP_Server:app --host 0.0.0.0 --port 8010"
timeout /t 4 /nobreak >NUL

REM Start A2UI Protocol Server (FastAPI - uses uvicorn internally via __main__)
echo [2/3] Starting A2UI Protocol Server on port 8020...
start "A2UI Protocol Server" cmd /k "cd /d "%WORKSPACE_DIR%" && set A2UI_PORT=8020 && "%VENV_PYTHON%" a2ui_protocol_server.py"
timeout /t 4 /nobreak >NUL

REM Start Flask Application
echo [3/3] Starting Flask Application on port 5000...
start "Flask App" cmd /k "cd /d "%WORKSPACE_DIR%" && set PAYPAL_MCP_PORT=8010 && set PAYPAL_MCP_HOST=localhost && set A2UI_PORT=8020 && "%VENV_PYTHON%" app.py"
timeout /t 4 /nobreak >NUL

echo.
echo ========================================
echo  All Servers Started!
echo ========================================
echo.
echo  Services Running:
echo  - Flask App:              http://localhost:5000
echo  - Flask App (remote):     http://%LOCAL_IP%:5000
echo  - A2UI Demo:              http://%LOCAL_IP%:5000/a2ui_demo
echo  - PayPal MCP Server:      http://localhost:8010
echo  - PayPal MCP (remote):    http://%LOCAL_IP%:8010
echo  - A2UI Protocol Server:   http://localhost:8020
echo  - A2UI Server (remote):   http://%LOCAL_IP%:8020
echo  - A2UI WebSocket:         ws://localhost:8020/ws/{session_id}
echo  - A2UI WebSocket (remote):ws://%LOCAL_IP%:8020/ws/{session_id}
echo  - PayPal Health Check:    http://%LOCAL_IP%:8010/health
echo  - A2UI Health Check:      http://%LOCAL_IP%:8020/
echo.
echo ========================================
echo  Press any key to stop all servers...
echo ========================================
pause >NUL

REM Stop all servers
echo.
echo Stopping all servers...
for /f "tokens=5" %%a in ('netstat -aon ^| find ":5000" ^| find "LISTENING"') do taskkill /F /PID %%a 2>NUL
for /f "tokens=5" %%a in ('netstat -aon ^| find ":8010" ^| find "LISTENING"') do taskkill /F /PID %%a 2>NUL
for /f "tokens=5" %%a in ('netstat -aon ^| find ":8020" ^| find "LISTENING"') do taskkill /F /PID %%a 2>NUL

echo All servers stopped.
echo.
pause

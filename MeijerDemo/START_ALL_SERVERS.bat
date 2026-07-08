@echo off
echo ========================================
echo  Starting All Servers with A2UI Protocol
echo ========================================
echo.

REM Detect local IP for display
for /f "tokens=4" %%a in ('route print 0.0.0.0 ^| findstr "0.0.0.0" ^| findstr /v "127." ^| findstr /v "On-link"') do set LOCAL_IP=%%a

REM Kill any existing processes on the ports
echo Checking for existing processes...
for /f "tokens=5" %%a in ('netstat -aon ^| find ":5000" ^| find "LISTENING"') do taskkill /F /PID %%a 2>NUL
for /f "tokens=5" %%a in ('netstat -aon ^| find ":8010" ^| find "LISTENING"') do taskkill /F /PID %%a 2>NUL
for /f "tokens=5" %%a in ('netstat -aon ^| find ":8020" ^| find "LISTENING"') do taskkill /F /PID %%a 2>NUL

echo.
echo ========================================
echo  Starting Servers...
echo ========================================
echo.

REM Start PayPal MCP Server
echo [1/3] Starting PayPal MCP Server on port 8010 (all interfaces)...
start "PayPal MCP Server" cmd /k "set PAYPAL_MCP_PORT=8010 && set PAYPAL_MCP_BIND_HOST=0.0.0.0 && python Paypal_MCP_Server.py"
timeout /t 3 /nobreak >NUL

REM Start A2UI Protocol Server
echo [2/3] Starting A2UI Protocol Server on port 8020 (all interfaces)...
start "A2UI Protocol Server" cmd /k "set A2UI_PORT=8020 && python a2ui_protocol_server.py"
timeout /t 3 /nobreak >NUL

REM Start Flask Application
echo [3/3] Starting Flask Application on port 5000 (all interfaces)...
start "Flask App" cmd /k "set PAYPAL_MCP_PORT=8010 && set A2UI_PORT=8020 && python app.py"
timeout /t 3 /nobreak >NUL

echo.
echo ========================================
echo  All Servers Started!
echo ========================================
echo.
echo  Services Running (accessible from ALL machines):
echo  - Flask App:              http://0.0.0.0:5000
echo  - Flask App (remote):     http://%LOCAL_IP%:5000
echo  - A2UI Demo:              http://%LOCAL_IP%:5000/a2ui_demo
echo  - PayPal MCP Server:      http://0.0.0.0:8010
echo  - PayPal MCP (remote):    http://%LOCAL_IP%:8010
echo  - A2UI Protocol Server:   http://0.0.0.0:8020
echo  - A2UI Server (remote):   http://%LOCAL_IP%:8020
echo  - A2UI WebSocket:         ws://0.0.0.0:8020/ws/{session_id}
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

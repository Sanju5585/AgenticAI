@echo off
echo ========================================
echo Starting All Servers
echo ========================================
echo.

echo Starting A2UI Protocol Server (port 8020)...
start "A2UI Server" cmd /k "python a2ui_protocol_server.py"
timeout /t 2 /nobreak >nul

echo Starting Flask Application (port 5000)...
start "Flask App" cmd /k "python app.py"
timeout /t 2 /nobreak >nul

echo.
echo ========================================
echo All Servers Started!
echo ========================================
echo A2UI Server: http://localhost:8020
echo Flask App: http://localhost:5000
echo.
echo Press any key to exit this window...
pause >nul

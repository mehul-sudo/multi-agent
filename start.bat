@echo off
cd /d "%~dp0"
title OrchestrAI Enterprise Launcher
echo ========================================================
echo   Starting OrchestrAI Enterprise Multi-Agent Assistant
echo ========================================================
echo.

echo Starting Flask Backend Server (Port 5000)...
start "OrchestrAI - Flask Backend" cmd /k "cd /d ""%~dp0"" && python run.py"

echo Starting React Vite Frontend (Port 5173)...
start "OrchestrAI - React Frontend" cmd /k "cd /d ""%~dp0frontend"" && npm run dev"

echo.
echo Both servers are starting!
echo Backend:  http://127.0.0.1:5000
echo Frontend: http://localhost:5173
echo.
echo Opening browser in 3 seconds...
timeout /t 3 /nobreak >nul
start http://localhost:5173

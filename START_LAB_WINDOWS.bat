@echo off
setlocal
cd /d "%~dp0"
title GIS Automation Lab - Start
if not exist "backend\.venv\Scripts\python.exe" goto NEED_SETUP
if not exist "frontend\node_modules\vite" goto NEED_SETUP
if not exist "backend\.env" goto NEED_SETUP
echo Starting Django and React in separate command windows...
start "GIS Lab - Backend" "%~dp0START_BACKEND_WINDOWS.bat"
start "GIS Lab - Frontend" "%~dp0START_FRONTEND_WINDOWS.bat"
echo.
echo Open http://localhost:5174
 echo Backend test: http://localhost:8100/api/health/
echo Keep both opened windows running. Close them with Ctrl+C to stop.
exit /b 0
:NEED_SETUP
echo Setup is not finished. First double-click SETUP_WINDOWS.bat.
pause
exit /b 1

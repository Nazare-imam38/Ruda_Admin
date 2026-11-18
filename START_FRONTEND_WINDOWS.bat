@echo off
cd /d "%~dp0frontend"
title GIS Automation Lab - React Frontend
if not exist "node_modules\vite" (
  echo Missing frontend packages. Run SETUP_WINDOWS.bat first.
  pause
  exit /b 1
)
echo React frontend available at http://127.0.0.1:5174/
call npm run dev
if errorlevel 1 (
  echo Frontend stopped with an error. Check the message above.
  pause
)

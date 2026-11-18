@echo off
setlocal
cd /d "%~dp0"
title GIS Automation Lab - One-Time Setup

echo ===================================================
echo GIS AUTOMATION LAB - NO DOCKER - ONE-TIME SETUP
echo ===================================================
echo Uses your local PostgreSQL and a NEW lab database.
echo Your RUDA projects and existing databases stay unchanged.
echo.

where py >nul 2>nul
if not errorlevel 1 (
    set "PYTHON_CMD=py -3"
) else (
    where python >nul 2>nul
    if errorlevel 1 (
        echo ERROR: Python 3.10+ was not found.
        echo Install Python for Windows and enable PATH, then run again.
        pause
        exit /b 1
    )
    set "PYTHON_CMD=python"
)
where npm >nul 2>nul
if errorlevel 1 (
    echo ERROR: Node.js/npm was not found.
    echo Install Node.js LTS, reopen the terminal, and try again.
    pause
    exit /b 1
)

echo [1/5] Creating isolated Python virtual environment...
if not exist "backend\.venv\Scripts\python.exe" (
    %PYTHON_CMD% -m venv "backend\.venv"
    if errorlevel 1 goto FAILED
)

echo [2/5] Installing Django and shapefile processing libraries...
"backend\.venv\Scripts\python.exe" -m pip install --upgrade pip
if errorlevel 1 goto FAILED
"backend\.venv\Scripts\python.exe" -m pip install -r "backend\requirements.txt"
if errorlevel 1 goto FAILED

echo [3/5] Configuring new PostGIS database (password will be requested)...
"backend\.venv\Scripts\python.exe" "scripts\configure_database.py"
if errorlevel 1 goto FAILED

echo [4/5] Running database migrations...
pushd backend
".venv\Scripts\python.exe" manage.py migrate --noinput
if errorlevel 1 (
    popd
    goto FAILED
)
".venv\Scripts\python.exe" manage.py check
if errorlevel 1 (
    popd
    goto FAILED
)
popd

echo Testing bundled shapefile samples...
"backend\.venv\Scripts\python.exe" scripts\verify_samples.py
if errorlevel 1 goto FAILED

echo [5/5] Installing React/MapLibre packages...
pushd frontend
call npm install
if errorlevel 1 (
    popd
    goto FAILED
)
popd

echo.
echo ==============================================
echo SETUP COMPLETED
 echo Next: double-click START_LAB_WINDOWS.bat
 echo Frontend: http://localhost:5174
 echo Backend:  http://localhost:8100/api/health/
echo ==============================================
pause
exit /b 0

:FAILED
echo.
echo ERROR: Setup stopped at the failed step.
echo Check the message above and run SETUP_WINDOWS.bat again.
pause
exit /b 1

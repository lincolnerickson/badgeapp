@echo off
title Badge Designer Web
echo Starting Badge Designer Web...
echo.
echo Once the server starts, your browser will open to http://localhost:5000
echo Press Ctrl+C to stop the server.
echo.

cd /d "%~dp0"

set PYTHON=

:: Try py launcher first (most reliable on Windows)
where py >nul 2>&1
if %errorlevel% equ 0 (
    set PYTHON=py
    goto :run
)

:: Try python on PATH
where python >nul 2>&1
if %errorlevel% equ 0 (
    set PYTHON=python
    goto :run
)

:: Try common install locations
if exist "%LOCALAPPDATA%\Programs\Python\Python312\python.exe" (
    set "PYTHON=%LOCALAPPDATA%\Programs\Python\Python312\python.exe"
    goto :run
)
if exist "%LOCALAPPDATA%\Programs\Python\Python311\python.exe" (
    set "PYTHON=%LOCALAPPDATA%\Programs\Python\Python311\python.exe"
    goto :run
)
if exist "%LOCALAPPDATA%\Programs\Python\Python310\python.exe" (
    set "PYTHON=%LOCALAPPDATA%\Programs\Python\Python310\python.exe"
    goto :run
)

echo ERROR: Python not found. Please install Python and add it to PATH.
pause
goto :eof

:run
echo Using: %PYTHON%
echo.

:: Open browser after a short delay (gives Flask time to start)
start "" /b cmd /c "timeout /t 2 /nobreak >nul && start http://localhost:5000"

"%PYTHON%" -m flask --app web.app run --host 127.0.0.1 --port 5000

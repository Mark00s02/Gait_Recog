@echo off
echo ============================================
echo   Gait Recognition System - Setup
echo ============================================
echo.

python --version 2>NUL
if %errorlevel% neq 0 (
    echo [ERROR] Python is not installed or not in PATH.
    echo Please install Python 3.8+ from https://python.org
    pause
    exit /b 1
)

echo [1/3] Creating virtual environment...
python -m venv venv
if %errorlevel% neq 0 (
    echo [ERROR] Failed to create virtual environment.
    pause
    exit /b 1
)

echo [2/3] Activating virtual environment...
call venv\Scripts\activate

echo [3/3] Installing dependencies...
pip install --upgrade pip
pip install -r requirements.txt

echo.
echo ============================================
echo   Setup complete!
echo   Run 'run.bat' to start the application.
echo ============================================
pause

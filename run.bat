@echo off
if exist venv\Scripts\activate (
    call venv\Scripts\activate
)
python main.py
if %errorlevel% neq 0 (
    echo.
    echo [ERROR] Application failed to start. Run setup.bat first.
    pause
)

@echo off
setlocal
cd /d "%~dp0"

if not exist ".venv\Scripts\python.exe" (
  py -m venv .venv
  if errorlevel 1 python -m venv .venv
  if errorlevel 1 (
    echo Could not create the virtual environment. Install Python and try again.
    pause
    exit /b 1
  )
)

call ".venv\Scripts\activate.bat"
python -m pip install --upgrade pip
if errorlevel 1 exit /b 1
python -m pip install -r requirements-dev.txt
if errorlevel 1 exit /b 1

echo.
echo Development environment is ready. Run run_dev.bat to launch without a console window.
pause

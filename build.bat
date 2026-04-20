@echo off
setlocal enabledelayedexpansion

echo ===================================
echo  FillablePDF Build Script
echo ===================================

:: Check for Python
python --version >nul 2>&1
if errorlevel 1 (
    echo ERROR: Python not found. Please install Python 3.10+.
    exit /b 1
)

:: Create virtual environment if it doesn't exist
if not exist ".venv" (
    echo Creating virtual environment...
    python -m venv .venv
)

:: Activate virtual environment
call .venv\Scripts\activate.bat

:: Upgrade pip silently
python -m pip install --upgrade pip --quiet

:: Install runtime dependencies + PyInstaller
echo Installing dependencies...
pip install -r requirements.txt pyinstaller --quiet

:: Run PyInstaller
echo Building executable...
pyinstaller FillablePDF.spec --noconfirm

echo.
echo Build complete.
echo Executable: dist\FillablePDF\FillablePDF.exe
endlocal

@echo off
setlocal enabledelayedexpansion

echo.
echo ============================================================
echo          JIBO AUTO-MOD TOOL - Windows Launcher
echo ============================================================
echo.

:: Check for Python
where python >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] Python not found! Please install Python 3.8+ from:
    echo         https://www.python.org/downloads/
    echo.
    echo Make sure to check "Add Python to PATH" during installation.
    pause
    exit /b 1
)

:: Check Python version
for /f "tokens=2 delims= " %%a in ('python --version 2^>^&1') do set PYVER=%%a
echo [INFO] Found Python %PYVER%

:: Check if running as admin (recommended for USB access)
net session >nul 2>&1
if %errorlevel% neq 0 (
    echo [WARNING] Not running as Administrator.
    echo          USB access may be limited. Consider right-clicking
    echo          and selecting "Run as administrator".
    echo.
)

:: Change to script directory
cd /d "%~dp0"

:: Run the Python tool
echo [INFO] Starting Jibo Auto-Mod Tool...
echo.

python jibo_automod.py %*

if %errorlevel% neq 0 (
    echo.
    echo [ERROR] Tool exited with error code %errorlevel%
    pause
)

endlocal

@echo off
setlocal enabledelayedexpansion

echo.
echo ============================================================
echo     JIBO AUTO-MOD - Windows Development Environment Setup
echo ============================================================
echo.

:: Check if running as admin
net session >nul 2>&1
if %errorlevel% neq 0 (
    echo [WARNING] Not running as Administrator.
    echo          Some installations may require admin rights.
    echo.
)

echo This script will help you set up the development environment
echo for building and running the Jibo Auto-Mod tool on Windows.
echo.

:: Check for Python
echo [1/4] Checking Python installation...
where python >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] Python not found!
    echo.
    echo Please install Python 3.8+ from:
    echo   https://www.python.org/downloads/
    echo.
    echo IMPORTANT: Check "Add Python to PATH" during installation!
    echo.
    echo After installing Python, run this script again.
    pause
    exit /b 1
) else (
    for /f "tokens=2 delims= " %%a in ('python --version 2^>^&1') do set PYVER=%%a
    echo [OK] Python !PYVER! found
)

:: Check for MSYS2
echo.
echo [2/4] Checking MSYS2 installation...
if exist "C:\msys64\usr\bin\bash.exe" (
    echo [OK] MSYS2 found at C:\msys64
    set MSYS2_PATH=C:\msys64
) else if exist "C:\msys32\usr\bin\bash.exe" (
    echo [OK] MSYS2 found at C:\msys32
    set MSYS2_PATH=C:\msys32
) else (
    echo [ERROR] MSYS2 not found!
    echo.
    echo Please install MSYS2 from:
    echo   https://www.msys2.org/
    echo.
    echo After installing:
    echo   1. Open "MSYS2 MINGW64" from Start Menu
    echo   2. Run: pacman -Syu
    echo   3. Run this script again
    pause
    exit /b 1
)

:: Install MSYS2 packages
echo.
echo [3/4] Installing required packages via MSYS2...
echo.
echo This will install: gcc, make, libusb, arm-none-eabi-gcc
echo.

set MSYS2_BASH=%MSYS2_PATH%\usr\bin\bash.exe

:: Create a temporary script for MSYS2
set TEMP_SCRIPT=%TEMP%\jibo_setup.sh
echo #!/bin/bash > "%TEMP_SCRIPT%"
echo echo "Updating package database..." >> "%TEMP_SCRIPT%"
echo pacman -Sy --noconfirm >> "%TEMP_SCRIPT%"
echo echo "Installing MinGW toolchain..." >> "%TEMP_SCRIPT%"
echo pacman -S --noconfirm --needed mingw-w64-x86_64-gcc mingw-w64-x86_64-make >> "%TEMP_SCRIPT%"
echo echo "Installing libusb..." >> "%TEMP_SCRIPT%"
echo pacman -S --noconfirm --needed mingw-w64-x86_64-libusb >> "%TEMP_SCRIPT%"
echo echo "Installing ARM toolchain..." >> "%TEMP_SCRIPT%"
echo pacman -S --noconfirm --needed mingw-w64-x86_64-arm-none-eabi-gcc >> "%TEMP_SCRIPT%"
echo echo "Done!" >> "%TEMP_SCRIPT%"

"%MSYS2_BASH%" -l -c "source '%TEMP_SCRIPT%'"
del "%TEMP_SCRIPT%"

:: Install Zadig info
echo.
echo [4/4] USB Driver Setup (Zadig)...
echo.
echo To communicate with Jibo in RCM mode, you need the WinUSB driver.
echo.
echo Steps:
echo   1. Download Zadig from: https://zadig.akeo.ie/
echo   2. Put Jibo in RCM mode (hold RCM + press power)
echo   3. Run Zadig
echo   4. Options ^> List All Devices
echo   5. Select "APX" from the dropdown
echo   6. Select "WinUSB" as the target driver
echo   7. Click "Replace Driver"
echo.

:: Final instructions
echo.
echo ============================================================
echo                    SETUP COMPLETE
echo ============================================================
echo.
echo To build Shofel and run the mod tool:
echo.
echo   1. Open "MSYS2 MINGW64" from Start Menu
echo   2. Navigate to this folder:
echo      cd /c/path/to/JiboAutoMod
echo   3. Build Shofel:
echo      cd Shofel ^&^& make
echo   4. Run the mod tool:
echo      python ../jibo_automod.py
echo.
echo Or use the batch launcher:
echo   jibo_automod.bat
echo.
echo NOTE: Some USB operations may require running as Administrator.
echo.
pause
endlocal

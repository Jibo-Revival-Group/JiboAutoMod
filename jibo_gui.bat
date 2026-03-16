@echo off
setlocal

REM Main GUI launcher (Main Panel)

set "SCRIPT_DIR=%~dp0"
set "VENV_PY=%SCRIPT_DIR%.venv\Scripts\python.exe"

if exist "%VENV_PY%" (
  "%VENV_PY%" -m gui.main_panel %*
  exit /b %ERRORLEVEL%
)

where py >nul 2>nul
if %ERRORLEVEL%==0 (
  py -3 -m gui.main_panel %*
  exit /b %ERRORLEVEL%
)

python -m gui.main_panel %*
exit /b %ERRORLEVEL%

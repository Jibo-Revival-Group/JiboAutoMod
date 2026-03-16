@echo off
setlocal

REM Wrapper for jibo_updater.py
REM Prefers the repo-local venv if it exists.

set "SCRIPT_DIR=%~dp0"
set "VENV_PY=%SCRIPT_DIR%.venv\Scripts\python.exe"

if exist "%VENV_PY%" (
  "%VENV_PY%" "%SCRIPT_DIR%jibo_updater.py" %*
  exit /b %ERRORLEVEL%
)

REM Prefer the Python launcher if available
where py >nul 2>nul
if %ERRORLEVEL%==0 (
  py -3 "%SCRIPT_DIR%jibo_updater.py" %*
  exit /b %ERRORLEVEL%
)

python "%SCRIPT_DIR%jibo_updater.py" %*
exit /b %ERRORLEVEL%

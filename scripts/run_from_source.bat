@echo off
rem Run from source with a console window (for development / troubleshooting)
cd /d "%~dp0.."
set "PY=py -3"
%PY% -c "import sys" >nul 2>nul || set "PY=python"
%PY% -m pip install --disable-pip-version-check -r requirements.txt
%PY% src\phone_display.py --no-tray %*
pause

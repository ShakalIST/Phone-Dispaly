@echo off
rem Local build of the installer (needs Python and Inno Setup 6)
cd /d "%~dp0.."
set "PY=py -3"
%PY% -c "import sys" >nul 2>nul || set "PY=python"
%PY% -m pip install --disable-pip-version-check -r requirements.txt pyinstaller || exit /b 1
%PY% tools\make_icon.py build\icon.ico || exit /b 1
%PY% -m PyInstaller --noconfirm --onedir --windowed --name PhoneDisplay --icon build\icon.ico --hidden-import pystray._win32 src\phone_display.py || exit /b 1
"%ProgramFiles(x86)%\Inno Setup 6\ISCC.exe" /DAppVersion=%1 installer\PhoneDisplay.iss || exit /b 1
echo.
echo Installer: installer\Output
pause

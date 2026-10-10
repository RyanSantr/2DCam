@echo off
cd /d "%~dp0\.."
if not exist ".venv\Scripts\python.exe" python -m venv .venv
if errorlevel 1 exit /b 1
call ".venv\Scripts\activate.bat"
python -c "import sys; sys.exit(0 if sys.version_info[:2] == (3, 12) else 1)"
if errorlevel 1 (
  echo Este codigo-fonte requer Python 3.12 de 64 bits. O executavel pronto nao precisa de Python.
  exit /b 1
)
python -m pip install -r requirements.txt
if errorlevel 1 exit /b 1
python -m PyInstaller --noconfirm --clean 2DCam.spec
if errorlevel 1 exit /b 1
echo Executavel pronto: dist\2DCamStudio\2DCamStudio.exe
pause

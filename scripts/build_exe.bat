@echo off
cd /d "%~dp0\.."
if not exist ".venv\Scripts\python.exe" (
  echo Criando ambiente virtual...
  python -m venv .venv
)
call ".venv\Scripts\activate.bat"
pip install -r requirements.txt
pyinstaller --noconfirm --clean --windowed --name AvatarCam2D --collect-binaries sounddevice --collect-data sounddevice app.py
echo.
echo Executavel gerado em dist\AvatarCam2D.exe

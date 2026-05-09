@echo off
cd /d "%~dp0\.."
if not exist ".venv\Scripts\python.exe" (
  echo Criando ambiente virtual...
  python -m venv .venv
)
call ".venv\Scripts\activate.bat"
pip install -r requirements.txt
if errorlevel 1 (
  echo Falha ao instalar dependencias.
  exit /b 1
)
pyinstaller --noconfirm --clean --onefile --windowed --name AvatarCam2D --collect-binaries sounddevice --collect-data sounddevice app.py
if errorlevel 1 (
  echo Falha ao gerar o executavel.
  exit /b 1
)
echo.
echo Executavel gerado em dist\AvatarCam2D.exe

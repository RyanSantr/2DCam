@echo off
cd /d "%~dp0\.."
if not exist ".venv\Scripts\python.exe" (
  echo Criando ambiente virtual...
  python -m venv .venv
)
call ".venv\Scripts\activate.bat"
python -c "import sys; sys.exit(0 if sys.version_info[:2] == (3, 12) else 1)"
if errorlevel 1 (
  echo Este codigo-fonte requer Python 3.12 de 64 bits. O executavel pronto nao precisa de Python.
  exit /b 1
)
pip install -r requirements.txt
if errorlevel 1 (
  echo Falha ao instalar dependencias.
  exit /b 1
)
python app.py

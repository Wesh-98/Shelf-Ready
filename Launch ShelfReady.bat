@echo off
setlocal ENABLEDELAYEDEXPANSION
set SCRIPT_DIR=%~dp0
set VENV=%SCRIPT_DIR%.venv
set PYGUI=%SCRIPT_DIR%ShelfReady_Unified_GUI.py
if not exist "%VENV%\Scripts\python.exe" (
  echo [INFO] Creating virtual environment...
  py -m venv "%VENV%"
)
echo [INFO] Installing / updating requirements...
"%VENV%\Scripts\python.exe" -m pip install --upgrade pip >nul
"%VENV%\Scripts\python.exe" -m pip install -r "%SCRIPT_DIR%requirements.txt"
echo [INFO] Launching ShelfReady...
"%VENV%\Scripts\python.exe" -u "%PYGUI%"

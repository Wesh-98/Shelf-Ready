@echo off
setlocal
set VENV=%~dp0.venv
echo [INFO] Installing AVIF/HEIC codec support via pillow-heif...
"%VENV%\Scripts\python.exe" -m pip install --only-binary=:all: "pillow-heif[avif]" || (
  echo [WARN] AVIF extras failed — installing base pillow-heif...
  "%VENV%\Scripts\python.exe" -m pip install --only-binary=:all: pillow-heif
)
echo [INFO] Done. If AVIF files still fail, try Python 3.12 via the main launcher.
pause

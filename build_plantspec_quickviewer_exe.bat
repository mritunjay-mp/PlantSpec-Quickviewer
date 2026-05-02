@echo off
setlocal
cd /d "%~dp0"

echo Installing/checking PyInstaller and required packages...
py -3 -m pip install pyinstaller numpy pandas pillow openpyxl matplotlib
if errorlevel 1 exit /b 1

echo Building PlantSpec Quickviewer exe...
py -3 -m PyInstaller ^
  --noconfirm ^
  --clean ^
  --windowed ^
  --name PlantSpecQuickviewer ^
  --add-data "analyze_labeled_multispectral.py;." ^
  --exclude-module tensorflow ^
  --exclude-module tensorboard ^
  --exclude-module torch ^
  --exclude-module torchvision ^
  --exclude-module torchaudio ^
  --exclude-module scipy ^
  --exclude-module IPython ^
  --exclude-module PyQt5 ^
  --exclude-module boto3 ^
  --exclude-module botocore ^
  --exclude-module onnxruntime ^
  --exclude-module sklearn ^
  --exclude-module pytest ^
  --exclude-module keras ^
  plantspec_quickviewer.py

echo.
echo Done. The executable should be in:
echo dist\PlantSpecQuickviewer\PlantSpecQuickviewer.exe



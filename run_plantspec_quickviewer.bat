@echo off
setlocal
cd /d "%~dp0"
py -3 plantspec_quickviewer.py
if errorlevel 1 (
  echo.
  echo Failed to start with "py -3". Trying python...
  python plantspec_quickviewer.py
)



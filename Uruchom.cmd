@echo off
cd /d "%~dp0"
py -3 -c "import sys, tkinter; assert sys.version_info >= (3,10)" >nul 2>&1
if errorlevel 1 (
  echo Zainstaluj Python 3.10 lub nowszy z python.org z opcjami Python Launcher oraz Tcl/Tk.
  pause
  exit /b 1
)
py -3 app.py
if errorlevel 1 pause

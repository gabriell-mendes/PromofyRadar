@echo off
cd /d %~dp0..
if exist .venv\Scripts\python.exe (set PY=.venv\Scripts\python.exe) else (set PY=python)
start "" cmd /c "timeout /t 2 >nul & start http://localhost:5500"
%PY% techdrop_server.py
pause

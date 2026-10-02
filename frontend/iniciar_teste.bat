@echo off
rem Abre o painel usando os scrapers de TESTE (sem navegador) no lugar dos reais.
cd /d %~dp0..
set TECHDROP_SCRAPER=scraper_teste_busca.py
set TECHDROP_SCRAPER_CATEGORIA=scraper_teste_categoria.py
set TECHDROP_SCRAPER_OFERTAS=scraper_teste_ofertas.py
if exist .venv\Scripts\python.exe (set PY=.venv\Scripts\python.exe) else (set PY=python)
start "" cmd /c "timeout /t 2 >nul & start http://localhost:5500"
%PY% techdrop_server.py
pause

@echo off
title Orquestrador de Downloads
echo ============================================================
echo           INICIANDO O ORQUESTRADOR DE DOWNLOADS
echo ============================================================
echo.
echo Abrindo seu painel interativo de organizacao...
echo.

cd /d "%~dp0"

if exist ".venv\Scripts\python.exe" (
    start "" http://localhost:8080/
    .venv\Scripts\python.exe orquestrador.py --servidor --sem-navegador
) else (
    start "" http://localhost:8080/
    python orquestrador.py --servidor --sem-navegador
)

if %ERRORLEVEL% NEQ 0 (
    echo.
    echo Ocorreu um problema ao iniciar o programa.
    pause
)

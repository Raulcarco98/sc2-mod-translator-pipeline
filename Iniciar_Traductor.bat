@echo off
title Traductor Mods StarCraft II
color 0A

:: Asegurarnos de que estamos en el directorio correcto
cd /d "%~dp0"

echo ==============================================
echo   Iniciando Traductor de Mods StarCraft II
echo ==============================================
echo.
echo Activando entorno virtual...

:: Activar entorno virtual y arrancar la interfaz usando pythonw 
:: (pythonw lanza el proceso sin abrir una ventana de consola molesta detrás)
call venv\Scripts\activate.bat
start "" pythonw interfaz.py

echo.
echo [+] Aplicacion lanzada con exito.
echo [*] Puedes cerrar esta ventana negra de forma segura.
timeout /t 3 >nul
exit

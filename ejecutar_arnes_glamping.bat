@echo off
rem Arnes fisico de glamping-imbabura-agent: unico arbitro de "fase completada".
rem Escribe governance\artefactos\data\.test_verdict.json y devuelve el Exit Code global.
setlocal
cd /d "%~dp0"
python scripts\arnes_glamping.py %*
set CODIGO=%ERRORLEVEL%
endlocal & exit /b %CODIGO%

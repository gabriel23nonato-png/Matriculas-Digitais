@echo off
title Sistema de Matriculas - Servidor
cd /d "%~dp0"
:inicio
echo [%date% %time%] Iniciando servidor...
python app.py
set CODIGO=%errorlevel%
echo [%date% %time%] Servidor parou. Codigo de saida: %CODIGO%>> reinicios.log
echo [%date% %time%] Servidor parou (codigo %CODIGO%). Reiniciando em 3 segundos... (feche esta janela para encerrar de vez)
timeout /t 3 /nobreak >nul
goto inicio

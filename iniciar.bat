@echo off
title Auto-Ping - Servidor Local
echo ==============================================
echo Iniciando o sistema de Gestao de Colaboradores...
echo ==============================================
echo.

:: Abre o navegador padrão no endereço do sistema
start http://localhost:5000

:: Inicia o servidor Python
python app.py

:: Caso o servidor feche, pausa a tela para ver se deu erro
pause

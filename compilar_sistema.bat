@echo off
echo ===================================================
echo   Compilador do Auto-Ping (Transformar em EXE)
echo ===================================================
echo.

echo 1. Verificando se o PyInstaller esta instalado...
pip install pyinstaller

echo.
echo 2. Iniciando a compilacao... Isso pode demorar alguns minutos.
echo Por favor, nao feche esta janela!
echo.

pyinstaller --name "AutoPing" --onefile --noconsole --add-data "static;static" --add-data "rdp_templates;rdp_templates" --icon=NONE app.py

echo.
echo ===================================================
echo   COMPILACAO CONCLUIDA!
echo ===================================================
echo.
echo O seu executavel final (AutoPing.exe) esta dentro da pasta "dist"
echo que acabou de ser criada (ou atualizada) aqui na pasta do projeto.
echo.
pause

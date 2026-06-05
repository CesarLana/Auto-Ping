@echo off
setlocal enabledelayedexpansion

if "%~1"=="" (
    echo.
    echo =======================================================
    echo   Auto-Ping - Localizador de Usuario (RACF) na Rede
    echo =======================================================
    echo   Uso: achar.bat [RACF]
    echo   Exemplo: achar.bat F123456
    echo.
    exit /b 1
)

set "RACF=%~1"
set "dc=%LOGONSERVER:\=%"

if "%dc%"=="" (
    echo [AVISO] Logon Server nao detectado (LOGONSERVER vazio).
    echo Tentando pesquisar no log de seguranca local...
    echo.
    wevtutil qe Security "/q:*[System[(EventID=4624)] and EventData[Data='%RACF%']]" /f:text /c:1 /rd:true | findstr /i "Endereço Address Ip Estação Workstation"
    exit /b 0
)

echo Buscando a ultima maquina de login do RACF %RACF% no servidor %dc%...
echo Isso pode levar alguns segundos...
echo.

wevtutil qe Security /r:%dc% "/q:*[System[(EventID=4624)] and EventData[Data='%RACF%']]" /f:text /c:1 /rd:true | findstr /i "Endereço Address Ip Estação Workstation"

if errorlevel 1 (
    echo.
    echo [INFO] Nenhum registro recente encontrado no servidor %dc%.
    echo Tentando buscar no log de seguranca local...
    echo.
    wevtutil qe Security "/q:*[System[(EventID=4624)] and EventData[Data='%RACF%']]" /f:text /c:1 /rd:true | findstr /i "Endereço Address Ip Estação Workstation"
)

endlocal

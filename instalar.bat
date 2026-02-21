@echo off
set DEST="%USERPROFILE%\Desktop\StockWare"

echo ------------------------------------------
echo INSTALADOR STOCKWARE
echo ------------------------------------------
echo.
echo Creando carpeta en Escritorio...
if not exist %DEST% mkdir %DEST%

echo.
echo Copiando archivos...
copy "dist\StockWare.exe" %DEST%
if errorlevel 1 (
    echo [ERROR] No se pudo copiar StockWare.exe. Intenta cerrar cualquier instancia abierta.
    pause
    exit /b
)

copy ".env" %DEST%
if errorlevel 1 (
    echo [ERROR] No se pudo copiar .env. Verifica que exista en la carpeta del proyecto.
    pause
    exit /b
)

echo.
echo [EXITO] Instalacion completada correctamente en:
echo %DEST%
echo.
echo Puedes abrir la carpeta y ejecutar StockWare.exe
pause
start "" %DEST%

@echo off
chcp 65001 >nul
setlocal EnableDelayedExpansion

:: =============================================================================
:: Aegis-Peru - Script de Actualizacion para Windows
:: =============================================================================
:: Actualiza la imagen y reinicia servicios sin perder datos
:: =============================================================================

title Aegis-Peru Update
color 0E

echo.
echo    ╔══════════════════════════════════════════════════════════════════╗
echo    ║                    AEGIS-PERU UPDATE                             ║
echo    ╚══════════════════════════════════════════════════════════════════╝
echo.

:: ── VERIFICAR ADMINISTRADOR ────────────────────────────────────────────────
net session >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] Ejecutar como Administrador.
    pause
    exit /b 1
)

:: ── PULL DE CODIGO ─────────────────────────────────────────────────────────
echo [1/5] Actualizando codigo fuente...

git pull origin main 2>nul
if %errorlevel% equ 0 (
    echo [OK] Codigo actualizado.
) else (
    echo [ADVERTENCIA] No se pudo actualizar via git. Verifica manualmente.
)
echo.

:: ── BACKUP PREVIO ──────────────────────────────────────────────────────────
echo [2/5] Creando backup de seguridad...

call scripts\backup.bat >nul 2>&1
echo [OK] Backup de seguridad creado.
echo.

:: ── DETENER SERVICIOS ──────────────────────────────────────────────────────
echo [3/5] Deteniendo servicios...

docker-compose down
echo [OK] Servicios detenidos.
echo.

:: ── RECONSTRUIR IMAGENES ───────────────────────────────────────────────────
echo [4/5] Reconstruyendo imagenes...

docker-compose build --no-cache
echo [OK] Imagenes reconstruidas.
echo.

:: ── INICIAR SERVICIOS ──────────────────────────────────────────────────────
echo [5/5] Iniciando servicios actualizados...

docker-compose up -d
echo [OK] Servicios iniciados.
echo.

:: ── VERIFICACION ───────────────────────────────────────────────────────────
timeout /t 30 /nobreak >nul

curl -s http://localhost:8000/health >nul 2>&1
if %errorlevel% equ 0 (
    echo [OK] API responde correctamente.
) else (
    echo [ADVERTENCIA] API no responde aun. Verifica logs.
)

echo.
echo [INFO] Actualizacion completada.
echo [INFO] Presiona cualquier tecla para salir...
pause >nul

endlocal

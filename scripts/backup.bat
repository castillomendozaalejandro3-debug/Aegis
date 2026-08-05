@echo off
chcp 65001 >nul
setlocal EnableDelayedExpansion

:: =============================================================================
:: Aegis-Peru - Script de Backup para Windows
:: =============================================================================
:: Ejecutar como Administrador
:: =============================================================================

title Aegis-Peru Backup
color 0B

echo.
echo    ╔══════════════════════════════════════════════════════════════════╗
echo    ║                    AEGIS-PERU BACKUP                             ║
echo    ╚══════════════════════════════════════════════════════════════════╝
echo.

:: ── VERIFICAR ADMINISTRADOR ────────────────────────────────────────────────
net session >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] Ejecutar como Administrador.
    pause
    exit /b 1
)

:: ── CREAR DIRECTORIO DE BACKUP ─────────────────────────────────────────────
set TIMESTAMP=%date:~-4,4%%date:~-10,2%%date:~-7,2%_%time:~0,2%%time:~3,2%%time:~6,2%
set TIMESTAMP=%TIMESTAMP: =0%
set BACKUP_DIR=backups\%TIMESTAMP%

if not exist "backups" mkdir "backups"
mkdir "%BACKUP_DIR%"

echo [INFO] Directorio de backup: %BACKUP_DIR%
echo.

:: ── BACKUP DE POSTGRESQL ───────────────────────────────────────────────────
echo [1/4] Backup de PostgreSQL...

docker-compose exec -T postgres pg_dump -U aegis -d aegis_peru > "%BACKUP_DIR%\postgres_backup.sql" 2>nul

if %errorlevel% equ 0 (
    echo [OK] PostgreSQL backup completado.
    for %%F in ("%BACKUP_DIR%\postgres_backup.sql") do (
        echo [INFO] Tamano: %%~zF bytes
    )
) else (
    echo [ERROR] Fallo backup de PostgreSQL.
)
echo.

:: ── BACKUP DE NEO4J ────────────────────────────────────────────────────────
echo [2/4] Backup de Neo4j...

docker-compose exec -T neo4j neo4j-admin database dump neo4j --to-path=/backups 2>nul

if %errorlevel% equ 0 (
    docker-compose cp neo4j:/backups "%BACKUP_DIR%\neo4j" 2>nul
    echo [OK] Neo4j backup completado.
) else (
    echo [ADVERTENCIA] Neo4j backup fallo. Intentando metodo alternativo...
    docker-compose exec -T neo4j cypher-shell -u neo4j -p %NEO4J_PASSWORD% "CALL apoc.meta.stats()" > "%BACKUP_DIR%\neo4j_stats.cypher" 2>nul
)
echo.

:: ── BACKUP DE EVIDENCIAS ───────────────────────────────────────────────────
echo [3/4] Backup de evidencias...

if exist "evidence" (
    xcopy /E /I /Y "evidence" "%BACKUP_DIR%\evidence" >nul 2>&1
    echo [OK] Evidencias respaldadas.
) else (
    echo [INFO] No hay evidencias para respaldar.
)
echo.

:: ── BACKUP DE CONFIGURACION ────────────────────────────────────────────────
echo [4/4] Backup de configuracion...

copy ".env" "%BACKUP_DIR%\.env.backup" >nul 2>&1
copy "docker-compose.yml" "%BACKUP_DIR%\docker-compose.yml.backup" >nul 2>&1
xcopy /E /I /Y "docker\certs" "%BACKUP_DIR%\certs" >nul 2>&1
xcopy /E /I /Y "secrets" "%BACKUP_DIR%\secrets" >nul 2>&1

echo [OK] Configuracion respaldada.
echo.

:: ── RESUMEN ────────────────────────────────────────────────────────────────
echo [INFO] Backup completado en: %BACKUP_DIR%
echo.

:: Listar archivos
dir /B "%BACKUP_DIR%"

echo.
echo [INFO] Presiona cualquier tecla para salir...
pause >nul

endlocal

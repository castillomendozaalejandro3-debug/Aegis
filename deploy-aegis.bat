@echo off
chcp 65001 >nul
setlocal EnableDelayedExpansion

:: =============================================================================
:: Aegis-Peru - Script de Despliegue Automatizado para Windows
:: =============================================================================
:: Ejecutar como Administrador despues de configurar .env
:: =============================================================================

title Aegis-Peru Deployment
color 0A

echo.
echo    ╔══════════════════════════════════════════════════════════════════╗
echo    ║                                                                  ║
echo    ║           A E G I S   -   P E R U   O S I N T                    ║
echo    ║                                                                  ║
echo    ║           Sistema de Inteligencia para Investigacion             ║
echo    ║           Criminal - Despliegue Automatizado                     ║
echo    ║                                                                  ║
echo    ╚══════════════════════════════════════════════════════════════════╝
echo.

:: ── VERIFICAR ADMINISTRADOR ────────────────────────────────────────────────
net session >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] Este script debe ejecutarse como Administrador.
    echo [INFO] Click derecho -^> "Ejecutar como administrador"
    pause
    exit /b 1
)

:: ── VERIFICAR PREREQUISITOS ────────────────────────────────────────────────
echo [1/10] Verificando prerequisitos...

docker --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] Docker no esta instalado.
    echo [INFO] Descarga Docker Desktop desde: https://www.docker.com/products/docker-desktop
    pause
    exit /b 1
)

docker-compose --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] Docker Compose no esta instalado.
    echo [INFO] Se incluye con Docker Desktop. Verifica la instalacion.
    pause
    exit /b 1
)

openssl version >nul 2>&1
if %errorlevel% neq 0 (
    echo [ADVERTENCIA] OpenSSL no encontrado. Instalando certificados pre-generados...
    echo [INFO] Descarga OpenSSL desde: https://slproweb.com/products/Win32OpenSSL.html
)

git --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [ADVERTENCIA] Git no encontrado. Algunas funciones pueden no estar disponibles.
)

echo [OK] Prerequisitos verificados.
echo.

:: ── VERIFICAR .env ─────────────────────────────────────────────────────────
echo [2/10] Verificando configuracion .env...

if not exist ".env" (
    echo [ERROR] Archivo .env no encontrado.
    echo [INFO] Copia .env.example a .env y configura los valores:
    echo.
    echo    copy .env.example .env
    echo    notepad .env
    echo.
    echo [INFO] Valores minimos requeridos:
    echo    - AEGIS_ENV=production
    echo    - JWT_SECRET=(minimo 32 caracteres)
    echo    - NEO4J_PASSWORD=(minimo 32 caracteres)
    echo    - POSTGRES_PASSWORD=(minimo 16 caracteres)
    echo    - OPENAI_API_KEY=(opcional, para VLM/NER)
    echo.
    pause
    exit /b 1
)

:: Verificar que JWT_SECRET no es el default
findstr /C:"JWT_SECRET=CAMBIAR" .env >nul 2>&1
if %errorlevel% equ 0 (
    echo [ERROR] JWT_SECRET aun tiene valor por defecto.
    echo [INFO] Edita .env y genera un secreto seguro.
    pause
    exit /b 1
)

echo [OK] Configuracion .env verificada.
echo.

:: ── CREAR DIRECTORIOS ──────────────────────────────────────────────────────
echo [3/10] Creando estructura de directorios...

if not exist "docker\certs" mkdir "docker\certs"
if not exist "secrets" mkdir "secrets"
if not exist "evidence" mkdir "evidence"
if not exist "uploads" mkdir "uploads"
if not exist "backups" mkdir "backups"
if not exist "docker\postgres\init" mkdir "docker\postgres\init"
if not exist "docker\kong" mkdir "docker\kong"
if not exist "docker\nginx" mkdir "docker\nginx"
if not exist "docker\prometheus" mkdir "docker\prometheus"
if not exist "docker\grafana\datasources" mkdir "docker\grafana\datasources"
if not exist "docker\grafana\dashboards" mkdir "docker\grafana\dashboards"
if not exist "docker\qdrant" mkdir "docker\qdrant"
if not exist "docker\neo4j" mkdir "docker\neo4j"

echo [OK] Directorios creados.
echo.

:: ── GENERAR CERTIFICADOS TLS ───────────────────────────────────────────────
echo [4/10] Generando certificados TLS/mTLS...

if exist "docker\certs\ca.crt" (
    echo [INFO] Certificados ya existen. Saltando generacion...
) else (
    openssl version >nul 2>&1
    if %errorlevel% equ 0 (
        :: Generar CA
        openssl genrsa -out docker\certs\ca.key 4096 2>nul
        openssl req -new -x509 -days 3650 -key docker\certs\ca.key -out docker\certs\ca.crt -subj "/C=PE/ST=Lima/L=Lima/O=Aegis-Peru/OU=Security/CN=aegis-ca" 2>nul

        :: Generar certificado servidor
        openssl genrsa -out docker\certs\server.key 2048 2>nul
        openssl req -new -key docker\certs\server.key -out docker\certs\server.csr -subj "/C=PE/ST=Lima/L=Lima/O=Aegis-Peru/OU=API/CN=aegis-peru.pnp.gob.pe" 2>nul
        openssl x509 -req -days 365 -in docker\certs\server.csr -CA docker\certs\ca.crt -CAkey docker\certs\ca.key -CAcreateserial -out docker\certs\server.crt 2>nul

        :: Generar certificado cliente (mTLS)
        openssl genrsa -out docker\certs\client.key 2048 2>nul
        openssl req -new -key docker\certs\client.key -out docker\certs\client.csr -subj "/C=PE/ST=Lima/L=Lima/O=Aegis-Peru/OU=Client/CN=aegis-client" 2>nul
        openssl x509 -req -days 365 -in docker\certs\client.csr -CA docker\certs\ca.crt -CAkey docker\certs\ca.key -CAcreateserial -out docker\certs\client.crt 2>nul

        :: Limpiar temporales
        del /Q docker\certs\*.csr 2>nul
        del /Q docker\certs\*.srl 2>nul

        echo [OK] Certificados TLS generados.
    ) else (
        echo [ADVERTENCIA] OpenSSL no disponible.
        echo [INFO] Por favor genera certificados manualmente o instala OpenSSL.
    )
)
echo.

:: ── GENERAR SECRETOS ───────────────────────────────────────────────────────
echo [5/10] Generando secretos de seguridad...

if exist "secrets\jwt_secret.txt" (
    echo [INFO] Secretos ya existen. Saltando generacion...
) else (
    :: Generar secretos aleatorios usando PowerShell
    powershell -Command "$bytes = New-Object byte[] 32; [System.Security.Cryptography.RandomNumberGenerator]::Create().GetBytes($bytes); [Convert]::ToBase64String($bytes) | Out-File -FilePath secrets\jwt_secret.txt -NoNewline" 2>nul
    powershell -Command "$bytes = New-Object byte[] 32; [System.Security.Cryptography.RandomNumberGenerator]::Create().GetBytes($bytes); [Convert]::ToBase64String($bytes) | Out-File -FilePath secrets\neo4j_password.txt -NoNewline" 2>nul
    powershell -Command "$bytes = New-Object byte[] 32; [System.Security.Cryptography.RandomNumberGenerator]::Create().GetBytes($bytes); [Convert]::ToBase64String($bytes) | Out-File -FilePath secrets\postgres_password.txt -NoNewline" 2>nul
    powershell -Command "$bytes = New-Object byte[] 32; [System.Security.Cryptography.RandomNumberGenerator]::Create().GetBytes($bytes); [Convert]::ToBase64String($bytes) | Out-File -FilePath secrets\redis_password.txt -NoNewline" 2>nul
    powershell -Command "$bytes = New-Object byte[] 24; [System.Security.Cryptography.RandomNumberGenerator]::Create().GetBytes($bytes); [Convert]::ToBase64String($bytes) | Out-File -FilePath secrets\grafana_password.txt -NoNewline" 2>nul

    echo [OK] Secretos generados.
)
echo.

:: ── VERIFICAR DOCKER ESTADO ────────────────────────────────────────────────
echo [6/10] Verificando estado de Docker...

docker info >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] Docker no esta corriendo.
    echo [INFO] Inicia Docker Desktop y espera a que este listo.
    pause
    exit /b 1
)

echo [OK] Docker esta corriendo.
echo.

:: ── DETENER SERVICIOS EXISTENTES ───────────────────────────────────────────
echo [7/10] Deteniendo servicios existentes...

docker-compose down --remove-orphans 2>nul
if %errorlevel% equ 0 (
    echo [OK] Servicios anteriores detenidos.
) else (
    echo [INFO] No habia servicios previos.
)
echo.

:: ── CONSTRUIR E INICIAR SERVICIOS ──────────────────────────────────────────
echo [8/10] Construyendo e iniciando servicios...
echo [INFO] Este proceso puede tomar 5-10 minutos la primera vez...
echo.

docker-compose up -d --build

if %errorlevel% neq 0 (
    echo [ERROR] Fallo al iniciar servicios.
    echo [INFO] Verifica los logs con: docker-compose logs
    pause
    exit /b 1
)

echo.
echo [OK] Servicios iniciados correctamente.
echo.

:: ── ESPERAR A QUE SERVICIOS ESTEN LISTOS ───────────────────────────────────
echo [9/10] Esperando a que los servicios esten listos...
echo [INFO] Esperando 45 segundos para inicializacion...

timeout /t 45 /nobreak >nul

:: Verificar health checks
echo [INFO] Verificando health checks...

:: PostgreSQL
docker-compose exec -T postgres pg_isready -U aegis >nul 2>&1
if %errorlevel% equ 0 (
    echo [OK] PostgreSQL: Healthy
) else (
    echo [ADVERTENCIA] PostgreSQL: No responde aun
)

:: Neo4j
curl -s http://localhost:7474 >nul 2>&1
if %errorlevel% equ 0 (
    echo [OK] Neo4j: Healthy
) else (
    echo [ADVERTENCIA] Neo4j: No responde aun
)

:: API Core
curl -s http://localhost:8000/health >nul 2>&1
if %errorlevel% equ 0 (
    echo [OK] API Core: Healthy
) else (
    echo [ADVERTENCIA] API Core: No responde aun
)

:: Qdrant
curl -s http://localhost:6333/healthz >nul 2>&1
if %errorlevel% equ 0 (
    echo [OK] Qdrant: Healthy
) else (
    echo [ADVERTENCIA] Qdrant: No responde aun
)

echo.

:: ── EJECUTAR MIGRACIONES ───────────────────────────────────────────────────
echo [10/10] Ejecutando migraciones de base de datos...

docker-compose exec -T core alembic upgrade head 2>nul
if %errorlevel% equ 0 (
    echo [OK] Migraciones ejecutadas.
) else (
    echo [ADVERTENCIA] No se pudieron ejecutar migraciones automaticamente.
    echo [INFO] Ejecuta manualmente: docker-compose exec core alembic upgrade head
)

echo.

:: ── RESUMEN FINAL ──────────────────────────────────────────────────────────
color 0E
echo    ╔══════════════════════════════════════════════════════════════════╗
echo    ║                    DESPLIEGUE COMPLETADO                         ║
echo    ╠══════════════════════════════════════════════════════════════════╣
echo    ║                                                                  ║
echo    ║  Servicios disponibles:                                          ║
echo    ║                                                                  ║
echo    ║  API REST:        http://localhost:8000                          ║
echo    ║  Documentacion:   http://localhost:8000/docs  (solo dev)         ║
echo    ║  Neo4j Browser:   http://localhost:7474                          ║
echo    ║  Grafana:         http://localhost:3000                          ║
echo    ║  Prometheus:      http://localhost:9090                          ║
echo    ║  Qdrant:          http://localhost:6333                          ║
echo    ║                                                                  ║
echo    ║  Credenciales por defecto:                                       ║
echo    ║  - Admin:         admin / changeme-2026!                         ║
echo    ║  - Grafana:       admin / (ver secrets\grafana_password.txt)     ║
echo    ║                                                                  ║
echo    ║  IMPORTANTE: Cambia las contrasenas inmediatamente               ║
echo    ║                                                                  ║
echo    ╠══════════════════════════════════════════════════════════════════╣
echo    ║  Comandos utiles:                                                ║
echo    ║                                                                  ║
echo    ║  Ver logs:        docker-compose logs -f                         ║
echo    ║  Detener:         docker-compose down                            ║
echo    ║  Reiniciar:       docker-compose restart                         ║
echo    ║  Backup DB:       scripts\backup.bat                             ║
echo    ║                                                                  ║
echo    ╚══════════════════════════════════════════════════════════════════╝
echo.

:: ── VERIFICACION FINAL ─────────────────────────────────────────────────────
echo [INFO] Realizando verificacion final...
curl -s http://localhost:8000/health > health_check.json 2>nul
if exist "health_check.json" (
    echo [OK] API responde correctamente.
    type health_check.json
    del health_check.json
) else (
    echo [ADVERTENCIA] API no responde aun. Espera unos minutos y verifica.
)

echo.
echo [INFO] Presiona cualquier tecla para salir...
pause >nul

endlocal

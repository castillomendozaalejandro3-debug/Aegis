# =============================================================================
# Project Aegis-Peru - Deploy Script para Windows (PowerShell)
# =============================================================================
# Script de despliegue completo para entornos Windows con Docker Desktop
# =============================================================================

[CmdletBinding()]
param(
    [ValidateSet("development", "staging", "production")]
    [string]$Environment = "production",
    
    [switch]$Build,
    [switch]$Rebuild,
    [switch]$Logs,
    [switch]$Stop,
    [switch]$Restart,
    [switch]$Status,
    [switch]$Clean,
    [switch]$Backup,
    [string]$BackupPath = ".\backups"
)

$ErrorActionPreference = "Stop"

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$ProjectDir = Split-Path -Parent $ScriptDir

function Write-Header($text) {
    Write-Host "`n=== $text ===" -ForegroundColor Cyan
}

function Write-Success($text) {
    Write-Host "  [OK] $text" -ForegroundColor Green
}

function Write-Warning($text) {
    Write-Host "  [!] $text" -ForegroundColor Yellow
}

function Write-Error($text) {
    Write-Host "  [X] $text" -ForegroundColor Red
}

# =============================================================================
# VERIFICACIONES INICIALES
# =============================================================================

Write-Header "Verificando entorno"

# Docker
$dockerInfo = docker info 2>$null
if (-not $?) {
    Write-Error "Docker no esta ejecutandose. Iniciar Docker Desktop."
    exit 1
}
Write-Success "Docker ejecutandose"

# Docker Compose
$composeVersion = docker compose version --short 2>$null
if (-not $composeVersion) {
    Write-Error "Docker Compose no disponible"
    exit 1
}
Write-Success "Docker Compose $composeVersion"

# .env
$envPath = Join-Path $ProjectDir ".env"
if (-not (Test-Path $envPath)) {
    Write-Error "Archivo .env no encontrado. Ejecutar setup.ps1 primero."
    exit 1
}
Write-Success ".env encontrado"

# =============================================================================
# FUNCIONES DE DESPLIEGUE
# =============================================================================

function Start-Deployment {
    Write-Header "Iniciando despliegue - Entorno: $Environment"
    
    Push-Location $ProjectDir
    
    try {
        # Exportar variables de entorno
        $env:AEGIS_ENV = $Environment
        
        # Verificar secretos
        $secretsDir = Join-Path $ProjectDir "secrets"
        $requiredSecrets = @(
            "jwt_secret.txt",
            "neo4j_password.txt",
            "postgres_password.txt",
            "redis_password.txt"
        )
        
        foreach ($secret in $requiredSecrets) {
            $path = Join-Path $secretsDir $secret
            if (-not (Test-Path $path)) {
                Write-Error "Secreto requerido no encontrado: $secret"
                exit 1
            }
        }
        Write-Success "Todos los secretos verificados"
        
        # Verificar certificados
        $certsDir = Join-Path $ProjectDir "docker\certs"
        $requiredCerts = @("ca.crt", "server.crt", "server.key", "client.crt", "client.key")
        foreach ($cert in $requiredCerts) {
            $path = Join-Path $certsDir $cert
            if (-not (Test-Path $path)) {
                Write-Error "Certificado requerido no encontrado: $cert"
                exit 1
            }
        }
        Write-Success "Todos los certificados verificados"
        
        # Construir imagenes si es necesario
        if ($Build -or $Rebuild) {
            Write-Header "Construyendo imagenes Docker"
            
            if ($Rebuild) {
                Write-Host "  Reconstruyendo sin cache..."
                docker compose build --no-cache
            } else {
                Write-Host "  Construyendo..."
                docker compose build
            }
            
            if (-not $?) {
                Write-Error "Error construyendo imagenes Docker"
                exit 1
            }
            Write-Success "Imagenes construidas"
        }
        
        # Iniciar servicios
        Write-Header "Iniciando servicios"
        docker compose up -d
        
        if (-not $?) {
            Write-Error "Error iniciando servicios"
            exit 1
        }
        Write-Success "Servicios iniciados"
        
        # Esperar a que los servicios esten saludables
        Write-Header "Esperando servicios saludables"
        $maxAttempts = 30
        $attempt = 0
        $healthy = $false
        
        while ($attempt -lt $maxAttempts -and -not $healthy) {
            Start-Sleep -Seconds 5
            $attempt++
            
            try {
                $health = Invoke-RestMethod -Uri "http://localhost:8000/health" -UseBasicParsing -TimeoutSec 5
                if ($health.status -eq "healthy") {
                    $healthy = $true
                    Write-Success "Todos los servicios saludables"
                } else {
                    Write-Warning "Servicios degradados (intento $attempt/$maxAttempts)"
                }
            } catch {
                Write-Warning "Esperando API... (intento $attempt/$maxAttempts)"
            }
        }
        
        if (-not $healthy) {
            Write-Warning "Timeout esperando servicios. Verificar logs con: .\scripts\deploy.ps1 -Logs"
        }
        
        # Ejecutar migraciones
        Write-Header "Ejecutando migraciones de base de datos"
        docker compose exec -T core alembic upgrade head
        
        if ($?) {
            Write-Success "Migraciones completadas"
        } else {
            Write-Warning "Error en migraciones (puede ser normal si ya estan aplicadas)"
        }
        
        # Resumen
        Write-Header "Despliegue Completado"
        
        Write-Host @"

  URLs de acceso:
    - API:        http://localhost:8000
    - API Docs:   http://localhost:8000/docs (solo development)
    - Grafana:    http://localhost:3000
    - Prometheus: http://localhost:9090
    - Neo4j:      http://localhost:7474
    - Kong:       http://localhost:8000 (API Gateway)
    - UI:         https://localhost:8443

  Comandos utiles:
    - Ver logs:      .\scripts\deploy.ps1 -Logs
    - Ver estado:    .\scripts\deploy.ps1 -Status
    - Reiniciar:     .\scripts\deploy.ps1 -Restart
    - Detener:       .\scripts\deploy.ps1 -Stop
    - Backup:        .\scripts\deploy.ps1 -Backup

  Credenciales por defecto (CAMBIAR INMEDIATAMENTE):
    - Usuario: admin
    - Password: changeme-2026!

"@ -ForegroundColor Green
        
    } finally {
        Pop-Location
    }
}

function Stop-Deployment {
    Write-Header "Deteniendo servicios"
    Push-Location $ProjectDir
    try {
        docker compose down
        Write-Success "Servicios detenidos"
    } finally {
        Pop-Location
    }
}

function Show-Logs {
    Write-Header "Mostrando logs"
    Push-Location $ProjectDir
    try {
        docker compose logs -f --tail=100
    } finally {
        Pop-Location
    }
}

function Show-Status {
    Write-Header "Estado de los servicios"
    Push-Location $ProjectDir
    try {
        docker compose ps
        Write-Host "`n"
        docker stats --no-stream
    } finally {
        Pop-Location
    }
}

function Restart-Services {
    Write-Header "Reiniciando servicios"
    Push-Location $ProjectDir
    try {
        docker compose restart
        Write-Success "Servicios reiniciados"
    } finally {
        Pop-Location
    }
}

function Clear-Environment {
    Write-Header "Limpiando entorno"
    Push-Location $ProjectDir
    try {
        docker compose down -v --remove-orphans
        docker system prune -f
        Write-Success "Entorno limpiado"
        Write-Warning "ADVERTENCIA: Los volumenes de datos fueron eliminados"
    } finally {
        Pop-Location
    }
}

function Backup-Data {
    Write-Header "Creando backup"
    
    $timestamp = Get-Date -Format "yyyyMMdd_HHmmss"
    $backupDir = Join-Path $BackupPath $timestamp
    
    New-Item -ItemType Directory -Path $backupDir -Force | Out-Null
    
    Write-Host "  Backup directory: $backupDir"
    
    # Backup PostgreSQL
    Write-Host "  Backing up PostgreSQL..."
    docker compose exec -T postgres pg_dump -U aegis aegis_peru | `
        Out-File -FilePath (Join-Path $backupDir "postgres_backup.sql") -Encoding utf8
    
    # Backup Neo4j
    Write-Host "  Backing up Neo4j..."
    docker compose exec -T neo4j neo4j-admin database dump neo4j --to-path=/tmp/backup
    docker cp aegis-neo4j:/tmp/backup (Join-Path $backupDir "neo4j")
    
    # Backup evidencias
    Write-Host "  Backing up evidencias..."
    $evidenceDir = Join-Path $ProjectDir "evidence"
    if (Test-Path $evidenceDir) {
        Compress-Archive -Path $evidenceDir -DestinationPath (Join-Path $backupDir "evidence.zip") -Force
    }
    
    # Backup .env y configs
    Write-Host "  Backing up configuracion..."
    Copy-Item (Join-Path $ProjectDir ".env") $backupDir
    Copy-Item (Join-Path $ProjectDir "docker-compose.yml") $backupDir
    
    Write-Success "Backup completado en: $backupDir"
}

# =============================================================================
# EJECUCION PRINCIPAL
# =============================================================================

if ($Stop) {
    Stop-Deployment
} elseif ($Logs) {
    Show-Logs
} elseif ($Status) {
    Show-Status
} elseif ($Restart) {
    Restart-Services
} elseif ($Clean) {
    Clear-Environment
} elseif ($Backup) {
    Backup-Data
} else {
    Start-Deployment
}

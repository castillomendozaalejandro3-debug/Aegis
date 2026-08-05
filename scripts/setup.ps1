# =============================================================================
# Project Aegis-Peru - Setup Script para Windows (PowerShell)
# =============================================================================
# Este script inicializa el entorno de Aegis-Peru de forma segura en Windows.
# Ejecutar UNA SOLA VEZ antes del primer despliegue.
# Requiere: PowerShell 7+, Docker Desktop, OpenSSL
# =============================================================================

[CmdletBinding()]
param(
    [switch]$SkipDockerCheck,
    [switch]$SkipCerts,
    [switch]$SkipSecrets,
    [string]$EnvFile = ".env"
)

$ErrorActionPreference = "Stop"
$ProgressPreference = "Continue"

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$ProjectDir = Split-Path -Parent $ScriptDir
$SecretsDir = Join-Path $ProjectDir "secrets"
$CertsDir = Join-Path $ProjectDir "docker\certs"

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

function Test-Command($cmd) {
    return [bool](Get-Command $cmd -ErrorAction SilentlyContinue)
}

function New-SecurePassword {
    $bytes = New-Object byte[] 32
    $rng = [System.Security.Cryptography.RandomNumberGenerator]::Create()
    $rng.GetBytes($bytes)
    return [Convert]::ToBase64String($bytes)
}

# =============================================================================
# INICIO
# =============================================================================

Write-Host @"
    ___    __________  _________    ____  ____
   /   |  /  _/ ____/ /_  __/   |  / __ \/ __ \
  / /| |  / // / __    / / / /| | / /_/ / / / /
 / ___ |_/ // /_/ /   / / / ___ |/ _, _/ /_/ /
/_/  |_/___/\____/   /_/ /_/  |_/_/ |_/_____/

Sistema de Inteligencia OSINT - Policia Nacional del Peru
"@ -ForegroundColor Blue

Write-Header "Verificando dependencias"

# Verificar PowerShell version
if ($PSVersionTable.PSVersion.Major -lt 7) {
    Write-Error "PowerShell 7+ requerido. Version actual: $($PSVersionTable.PSVersion)"
    Write-Host "Descargar desde: https://github.com/PowerShell/PowerShell/releases"
    exit 1
}
Write-Success "PowerShell $($PSVersionTable.PSVersion)"

# Verificar Docker
if (-not $SkipDockerCheck) {
    if (-not (Test-Command "docker")) {
        Write-Error "Docker no encontrado. Instalar Docker Desktop:"
        Write-Host "  https://www.docker.com/products/docker-desktop"
        exit 1
    }
    
    $dockerVersion = docker version --format '{{.Server.Version}}' 2>$null
    if (-not $dockerVersion) {
        Write-Error "Docker no esta ejecutandose. Iniciar Docker Desktop."
        exit 1
    }
    Write-Success "Docker $dockerVersion"
    
    # Verificar Docker Compose
    $composeVersion = docker compose version --short 2>$null
    if (-not $composeVersion) {
        Write-Warning "Docker Compose plugin no encontrado"
    } else {
        Write-Success "Docker Compose $composeVersion"
    }
}

# Verificar OpenSSL
if (-not (Test-Command "openssl")) {
    Write-Warning "OpenSSL no encontrado. Instalar via winget:"
    Write-Host "  winget install ShiningLight.OpenSSL"
    Write-Host "O descargar desde: https://slproweb.com/products/Win32OpenSSL.html"
    
    # Intentar usar openssl de Git
    $gitOpenssl = "C:\Program Files\Git\usr\bin\openssl.exe"
    if (Test-Path $gitOpenssl) {
        $env:PATH = "$env:PATH;C:\Program Files\Git\usr\bin"
        Write-Success "OpenSSL encontrado en Git installation"
    } else {
        Write-Error "OpenSSL requerido para generar certificados"
        exit 1
    }
} else {
    Write-Success "OpenSSL encontrado"
}

# =============================================================================
# CREAR DIRECTORIOS
# =============================================================================

Write-Header "Creando directorios"

$dirs = @(
    $SecretsDir,
    $CertsDir,
    (Join-Path $ProjectDir "evidence"),
    (Join-Path $ProjectDir "uploads"),
    (Join-Path $ProjectDir "docker\postgres\init"),
    (Join-Path $ProjectDir "docker\kong"),
    (Join-Path $ProjectDir "docker\nginx"),
    (Join-Path $ProjectDir "docker\prometheus"),
    (Join-Path $ProjectDir "docker\grafana\dashboards"),
    (Join-Path $ProjectDir "docker\grafana\datasources"),
    (Join-Path $ProjectDir "docker\qdrant")
)

foreach ($dir in $dirs) {
    if (-not (Test-Path $dir)) {
        New-Item -ItemType Directory -Path $dir -Force | Out-Null
        Write-Success "Creado: $dir"
    } else {
        Write-Success "Existe: $dir"
    }
}

# =============================================================================
# GENERAR CERTIFICADOS TLS
# =============================================================================

if (-not $SkipCerts) {
    Write-Header "Generando certificados TLS"
    
    Push-Location $CertsDir
    
    try {
        if (-not (Test-Path "ca.crt")) {
            Write-Host "  Generando CA..."
            openssl genrsa -out ca.key 4096 2>$null
            openssl req -new -x509 -days 3650 -key ca.key -out ca.crt `
                -subj "/C=PE/ST=Lima/L=Lima/O=Aegis-Peru/OU=Security/CN=aegis-ca" 2>$null
            Write-Success "CA generada"
        } else {
            Write-Success "CA ya existe"
        }
        
        if (-not (Test-Path "server.crt")) {
            Write-Host "  Generando certificado servidor..."
            openssl genrsa -out server.key 2048 2>$null
            openssl req -new -key server.key -out server.csr `
                -subj "/C=PE/ST=Lima/L=Lima/O=Aegis-Peru/OU=API/CN=aegis-peru.pnp.gob.pe" 2>$null
            openssl x509 -req -days 365 -in server.csr -CA ca.crt -CAkey ca.key `
                -CAcreateserial -out server.crt 2>$null
            Write-Success "Certificado servidor generado"
        } else {
            Write-Success "Certificado servidor ya existe"
        }
        
        if (-not (Test-Path "client.crt")) {
            Write-Host "  Generando certificado cliente (mTLS)..."
            openssl genrsa -out client.key 2048 2>$null
            openssl req -new -key client.key -out client.csr `
                -subj "/C=PE/ST=Lima/L=Lima/O=Aegis-Peru/OU=Client/CN=aegis-client" 2>$null
            openssl x509 -req -days 365 -in client.csr -CA ca.crt -CAkey ca.key `
                -CAcreateserial -out client.crt 2>$null
            Write-Success "Certificado cliente generado"
        } else {
            Write-Success "Certificado cliente ya existe"
        }
        
        # Limpiar archivos temporales
        Remove-Item -Path "*.csr", "*.srl" -ErrorAction SilentlyContinue
        
        # Establecer permisos (en Windows, ACLs)
        $keyFiles = Get-ChildItem -Path "*.key"
        foreach ($file in $keyFiles) {
            $acl = Get-Acl $file.FullName
            $acl.SetAccessRuleProtection($true, $false)
            
            # Solo el owner tiene acceso
            $rule = New-Object System.Security.AccessControl.FileSystemAccessRule(
                $env:USERNAME, "Read", "Allow"
            )
            $acl.SetAccessRule($rule)
            Set-Acl $file.FullName $acl
        }
        
        Write-Success "Permisos configurados"
        
    } finally {
        Pop-Location
    }
} else {
    Write-Warning "Generacion de certificados omitida"
}

# =============================================================================
# GENERAR SECRETOS
# =============================================================================

if (-not $SkipSecrets) {
    Write-Header "Generando secretos seguros"
    
    $secrets = @{
        "jwt_secret.txt" = { New-SecurePassword }
        "neo4j_password.txt" = { New-SecurePassword }
        "postgres_password.txt" = { New-SecurePassword }
        "redis_password.txt" = { New-SecurePassword }
        "grafana_password.txt" = { (New-SecurePassword).Substring(0, 24) }
    }
    
    foreach ($secretFile in $secrets.Keys) {
        $path = Join-Path $SecretsDir $secretFile
        if (-not (Test-Path $path)) {
            $value = & $secrets[$secretFile]
            $value | Out-File -FilePath $path -Encoding utf8 -NoNewline
            
            # Establecer permisos restrictivos
            $acl = Get-Acl $path
            $acl.SetAccessRuleProtection($true, $false)
            $rule = New-Object System.Security.AccessControl.FileSystemAccessRule(
                $env:USERNAME, "Read", "Allow"
            )
            $acl.SetAccessRule($rule)
            Set-Acl $path $acl
            
            Write-Success "$secretFile generado"
        } else {
            Write-Success "$secretFile ya existe"
        }
    }
} else {
    Write-Warning "Generacion de secretos omitida"
}

# =============================================================================
# CREAR .ENV
# =============================================================================

Write-Header "Configurando archivo .env"

$envPath = Join-Path $ProjectDir ".env"
$envExamplePath = Join-Path $ProjectDir ".env.example"

if (-not (Test-Path $envPath)) {
    if (Test-Path $envExamplePath) {
        Copy-Item $envExamplePath $envPath
        Write-Success ".env creado desde template"
        
        Write-Host "`n  ⚠️  IMPORTANTE: Editar $envPath con valores correctos:" -ForegroundColor Yellow
        Write-Host "     - POSTGRES_PASSWORD"
        Write-Host "     - NEO4J_PASSWORD"
        Write-Host "     - REDIS_PASSWORD"
        Write-Host "     - JWT_SECRET"
        Write-Host "     - OPENAI_API_KEY (opcional)"
        Write-Host "     - SHODAN_API_KEY (opcional)"
    } else {
        Write-Warning ".env.example no encontrado. Creando .env basico..."
        @"
# Aegis-Peru Environment Configuration
AEGIS_ENV=production
POSTGRES_DSN=postgresql+asyncpg://aegis:CHANGE_ME@postgres:5432/aegis_peru
NEO4J_URI=bolt://neo4j:7687
NEO4J_USER=neo4j
NEO4J_PASSWORD=CHANGE_ME_MIN_32_CHARS
REDIS_URL=redis://:CHANGE_ME@redis:6379/0
JWT_SECRET=CHANGE_ME_GENERATE_NEW_SECRET_MIN_32_CHARS
OPENAI_API_KEY=
SHODAN_API_KEY=
LOG_LEVEL=INFO
"@ | Out-File -FilePath $envPath -Encoding utf8
        Write-Success ".env basico creado"
    }
} else {
    Write-Success ".env ya existe"
}

# =============================================================================
# VERIFICAR PERMISOS
# =============================================================================

Write-Header "Verificando permisos"

# Secrets
$secretFiles = Get-ChildItem -Path $SecretsDir -File -ErrorAction SilentlyContinue
foreach ($file in $secretFiles) {
    $acl = Get-Acl $file.FullName
    $accessRules = $acl.Access | Where-Object { $_.IdentityReference -notmatch $env:USERNAME }
    if ($accessRules) {
        Write-Warning "Permisos restrictivos aplicados a $($file.Name)"
    }
}
Write-Success "Permisos verificados"

# =============================================================================
# RESUMEN
# =============================================================================

Write-Header "Setup Completado"

Write-Host @"

  Proximos pasos:
    1. Editar $(Join-Path $ProjectDir ".env") con valores de produccion
    2. Configurar API keys externas (OPENAI, SHODAN, CENSYS)
    3. Ejecutar: docker-compose up -d
    4. Verificar: Invoke-RestMethod -Uri 'http://localhost:8000/health' -UseBasicParsing
    5. Cambiar contrasena de admin inmediatamente

  Seguridad:
    - Secretos almacenados en: $SecretsDir
    - Certificados almacenados en: $CertsDir
    - NUNCA subir .env ni secretos al repositorio

  Para cambiar contrasena de admin:
    docker-compose exec postgres psql -U aegis -d aegis_peru
    UPDATE users SET password_hash = '\$2b\$12\$...' WHERE username = 'admin';

"@ -ForegroundColor Green

Write-Host "  Presione cualquier tecla para salir..." -ForegroundColor Cyan
$null = $Host.UI.RawUI.ReadKey("NoEcho,IncludeKeyDown")

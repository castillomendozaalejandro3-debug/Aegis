#!/bin/bash
# =============================================================================
# Project Aegis-Peru - Setup Script
# =============================================================================
# Este script inicializa el entorno de Aegis-Peru de forma segura.
# Ejecutar UNA SOLA VEZ antes del primer despliegue.
# =============================================================================

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
SECRETS_DIR="$PROJECT_DIR/secrets"
CERTS_DIR="$PROJECT_DIR/docker/certs"

echo "=== Aegis-Peru Setup ==="
echo "Directorio del proyecto: $PROJECT_DIR"
echo ""

# ── VERIFICAR DEPENDENCIAS ─────────────────────────────────────────────────
command -v openssl >/dev/null 2>&1 || { echo "ERROR: openssl no esta instalado"; exit 1; }
command -v docker >/dev/null 2>&1 || { echo "ERROR: docker no esta instalado"; exit 1; }
command -v docker-compose >/dev/null 2>&1 || { echo "ERROR: docker-compose no esta instalado"; exit 1; }

# ── CREAR DIRECTORIOS NECESARIOS ──────────────────────────────────────────
echo "[1/6] Creando directorios..."
mkdir -p "$SECRETS_DIR"
mkdir -p "$CERTS_DIR"
mkdir -p "$PROJECT_DIR/evidence"
mkdir -p "$PROJECT_DIR/uploads"
chmod 700 "$SECRETS_DIR"
chmod 700 "$CERTS_DIR"
chmod 700 "$PROJECT_DIR/evidence"
chmod 700 "$PROJECT_DIR/uploads"

# ── GENERAR CERTIFICADOS TLS ──────────────────────────────────────────────
echo "[2/6] Generando certificados TLS..."
if [ ! -f "$CERTS_DIR/ca.crt" ]; then
    # Generar CA
    openssl genrsa -out "$CERTS_DIR/ca.key" 4096
    openssl req -new -x509 -days 3650 -key "$CERTS_DIR/ca.key" \
        -out "$CERTS_DIR/ca.crt" \
        -subj "/C=PE/ST=Lima/L=Lima/O=Aegis-Peru/OU=Security/CN=aegis-ca"

    # Generar certificado del servidor
    openssl genrsa -out "$CERTS_DIR/server.key" 2048
    openssl req -new -key "$CERTS_DIR/server.key" \
        -out "$CERTS_DIR/server.csr" \
        -subj "/C=PE/ST=Lima/L=Lima/O=Aegis-Peru/OU=API/CN=aegis-peru.pnp.gob.pe"
    openssl x509 -req -days 365 -in "$CERTS_DIR/server.csr" \
        -CA "$CERTS_DIR/ca.crt" -CAkey "$CERTS_DIR/ca.key" \
        -CAcreateserial -out "$CERTS_DIR/server.crt"

    # Generar certificado del cliente (mTLS)
    openssl genrsa -out "$CERTS_DIR/client.key" 2048
    openssl req -new -key "$CERTS_DIR/client.key" \
        -out "$CERTS_DIR/client.csr" \
        -subj "/C=PE/ST=Lima/L=Lima/O=Aegis-Peru/OU=Client/CN=aegis-client"
    openssl x509 -req -days 365 -in "$CERTS_DIR/client.csr" \
        -CA "$CERTS_DIR/ca.crt" -CAkey "$CERTS_DIR/ca.key" \
        -CAcreateserial -out "$CERTS_DIR/client.crt"

    # Limpiar archivos temporales
    rm -f "$CERTS_DIR/server.csr" "$CERTS_DIR/client.csr" "$CERTS_DIR/ca.srl"

    chmod 600 "$CERTS_DIR"/*.key
    chmod 644 "$CERTS_DIR"/*.crt

    echo "  Certificados generados en $CERTS_DIR"
else
    echo "  Certificados ya existen, saltando..."
fi

# ── GENERAR SECRETOS ──────────────────────────────────────────────────────
echo "[3/6] Generando secretos..."

generate_secret() {
    openssl rand -base64 32 | tr -d '\n'
}

# JWT Secret
if [ ! -f "$SECRETS_DIR/jwt_secret.txt" ]; then
    generate_secret > "$SECRETS_DIR/jwt_secret.txt"
    chmod 600 "$SECRETS_DIR/jwt_secret.txt"
    echo "  JWT secret generado"
else
    echo "  JWT secret ya existe, saltando..."
fi

# Neo4j Password
if [ ! -f "$SECRETS_DIR/neo4j_password.txt" ]; then
    generate_secret > "$SECRETS_DIR/neo4j_password.txt"
    chmod 600 "$SECRETS_DIR/neo4j_password.txt"
    echo "  Neo4j password generado"
else
    echo "  Neo4j password ya existe, saltando..."
fi

# PostgreSQL Password
if [ ! -f "$SECRETS_DIR/postgres_password.txt" ]; then
    generate_secret > "$SECRETS_DIR/postgres_password.txt"
    chmod 600 "$SECRETS_DIR/postgres_password.txt"
    echo "  PostgreSQL password generado"
else
    echo "  PostgreSQL password ya existe, saltando..."
fi

# Redis Password
if [ ! -f "$SECRETS_DIR/redis_password.txt" ]; then
    generate_secret > "$SECRETS_DIR/redis_password.txt"
    chmod 600 "$SECRETS_DIR/redis_password.txt"
    echo "  Redis password generado"
else
    echo "  Redis password ya existe, saltando..."
fi

# Grafana Password
if [ ! -f "$SECRETS_DIR/grafana_password.txt" ]; then
    generate_secret | cut -c1-24 > "$SECRETS_DIR/grafana_password.txt"
    chmod 600 "$SECRETS_DIR/grafana_password.txt"
    echo "  Grafana password generado"
else
    echo "  Grafana password ya existe, saltando..."
fi

# ── CREAR .ENV ────────────────────────────────────────────────────────────
echo "[4/6] Configurando .env..."
if [ ! -f "$PROJECT_DIR/.env" ]; then
    cp "$PROJECT_DIR/.env.example" "$PROJECT_DIR/.env"
    echo "  .env creado desde template"
    echo ""
    echo "  ⚠️  IMPORTANTE: Edite $PROJECT_DIR/.env con los valores correctos:"
    echo "     - POSTGRES_PASSWORD"
    echo "     - NEO4J_PASSWORD"
    echo "     - REDIS_PASSWORD"
    echo "     - JWT_SECRET"
    echo "     - OPENAI_API_KEY (opcional)"
    echo "     - SHODAN_API_KEY (opcional)"
    echo ""
else
    echo "  .env ya existe, saltando..."
fi

# ── VERIFICAR PERMISOS ────────────────────────────────────────────────────
echo "[5/6] Verificando permisos..."
chmod 700 "$SECRETS_DIR"
chmod 600 "$SECRETS_DIR"/*.txt
chmod 700 "$CERTS_DIR"
chmod 600 "$CERTS_DIR"/*.key
chmod 644 "$CERTS_DIR"/*.crt
echo "  Permisos configurados correctamente"

# ── RESUMEN ────────────────────────────────────────────────────────────────
echo ""
echo "=== Setup Completado ==="
echo ""
echo "Proximos pasos:"
echo "  1. Edite $PROJECT_DIR/.env con los valores de produccion"
echo "  2. Configure las API keys externas (OPENAI, SHODAN, CENSYS)"
echo "  3. Ejecute: docker-compose up -d"
echo "  4. Verifique: curl -k https://localhost/health"
echo "  5. Cambie la contrasena del usuario admin inmediatamente"
echo ""
echo "Seguridad:"
echo "  - Los secretos se almacenan en $SECRETS_DIR (permisos 600)"
echo "  - Los certificados se almacenan en $CERTS_DIR"
echo "  - NUNCA suba .env ni secretos al repositorio"
echo ""
echo "Para cambiar la contrasena de admin:"
echo "  docker-compose exec postgres psql -U aegis -d aegis_peru"
echo "  UPDATE users SET password_hash = '\$2b\$12\$...' WHERE username = 'admin';"
echo ""

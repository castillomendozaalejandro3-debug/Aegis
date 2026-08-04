#!/bin/bash
# =============================================================================
# Aegis-Peru - Generador de Certificados TLS/mTLS
# =============================================================================
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CERTS_DIR="$(dirname "$SCRIPT_DIR")/docker/certs"

mkdir -p "$CERTS_DIR"
cd "$CERTS_DIR"

echo "Generando certificados TLS para Aegis-Peru..."

# CA
openssl genrsa -out ca.key 4096
openssl req -new -x509 -days 3650 -key ca.key -out ca.crt \
    -subj "/C=PE/ST=Lima/L=Lima/O=Aegis-Peru/OU=Security/CN=aegis-ca"

# Servidor
openssl genrsa -out server.key 2048
openssl req -new -key server.key -out server.csr \
    -subj "/C=PE/ST=Lima/L=Lima/O=Aegis-Peru/OU=API/CN=aegis-peru.pnp.gob.pe"
openssl x509 -req -days 365 -in server.csr -CA ca.crt -CAkey ca.key \
    -CAcreateserial -out server.crt

# Cliente (mTLS)
openssl genrsa -out client.key 2048
openssl req -new -key client.key -out client.csr \
    -subj "/C=PE/ST=Lima/L=Lima/O=Aegis-Peru/OU=Client/CN=aegis-client"
openssl x509 -req -days 365 -in client.csr -CA ca.crt -CAkey ca.key \
    -CAcreateserial -out client.crt

# Limpiar
rm -f *.csr *.srl

chmod 600 *.key
chmod 644 *.crt

echo "Certificados generados en $CERTS_DIR"
ls -la "$CERTS_DIR"

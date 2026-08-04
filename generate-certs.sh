#!/bin/bash
# Project Aegis-Peru - Generador de certificados mTLS
set -e

DOMAIN="${1:-aegis-peru.local}"
CERT_DIR="docker/certs"
DAYS=365
KEY_SIZE=4096

echo "=== Generando certificados TLS para ${DOMAIN} ==="
mkdir -p "${CERT_DIR}"

# 1. CA
openssl genrsa -out "${CERT_DIR}/ca.key" ${KEY_SIZE}
openssl req -new -x509 -days ${DAYS} -key "${CERT_DIR}/ca.key"     -out "${CERT_DIR}/ca.crt"     -subj "/C=PE/ST=Lima/L=Lima/O=PNP/OU=Aegis-Peru/CN=Aegis-Peru Root CA"     -sha384

# 2. Servidor
openssl genrsa -out "${CERT_DIR}/server.key" ${KEY_SIZE}
openssl req -new -key "${CERT_DIR}/server.key"     -out "${CERT_DIR}/server.csr"     -subj "/C=PE/ST=Lima/L=Lima/O=PNP/OU=Aegis-Peru/CN=${DOMAIN}"
openssl x509 -req -in "${CERT_DIR}/server.csr"     -CA "${CERT_DIR}/ca.crt" -CAkey "${CERT_DIR}/ca.key"     -CAcreateserial -out "${CERT_DIR}/server.crt"     -days ${DAYS} -sha384     -extfile <(printf "subjectAltName=DNS:${DOMAIN},DNS:*.${DOMAIN},IP:127.0.0.1,IP:172.20.0.10")

# 3. Cliente mTLS
openssl genrsa -out "${CERT_DIR}/client.key" ${KEY_SIZE}
openssl req -new -key "${CERT_DIR}/client.key"     -out "${CERT_DIR}/client.csr"     -subj "/C=PE/ST=Lima/L=Lima/O=PNP/OU=Aegis-Peru/CN=aegis-client"
openssl x509 -req -in "${CERT_DIR}/client.csr"     -CA "${CERT_DIR}/ca.crt" -CAkey "${CERT_DIR}/ca.key"     -CAcreateserial -out "${CERT_DIR}/client.crt"     -days ${DAYS} -sha384

# 4. Neo4j
openssl genrsa -out "${CERT_DIR}/neo4j.key" ${KEY_SIZE}
openssl req -new -key "${CERT_DIR}/neo4j.key"     -out "${CERT_DIR}/neo4j.csr"     -subj "/C=PE/ST=Lima/L=Lima/O=PNP/OU=Aegis-Peru/CN=neo4j.aegis-peru.local"
openssl x509 -req -in "${CERT_DIR}/neo4j.csr"     -CA "${CERT_DIR}/ca.crt" -CAkey "${CERT_DIR}/ca.key"     -CAcreateserial -out "${CERT_DIR}/neo4j.crt"     -days ${DAYS} -sha384

# 5. Qdrant
openssl genrsa -out "${CERT_DIR}/qdrant.key" ${KEY_SIZE}
openssl req -new -key "${CERT_DIR}/qdrant.key"     -out "${CERT_DIR}/qdrant.csr"     -subj "/C=PE/ST=Lima/L=Lima/O=PNP/OU=Aegis-Peru/CN=qdrant.aegis-peru.local"
openssl x509 -req -in "${CERT_DIR}/qdrant.csr"     -CA "${CERT_DIR}/ca.crt" -CAkey "${CERT_DIR}/ca.key"     -CAcreateserial -out "${CERT_DIR}/qdrant.crt"     -days ${DAYS} -sha384

rm -f "${CERT_DIR}"/*.csr "${CERT_DIR}"/*.srl
chmod 600 "${CERT_DIR}"/*.key
chmod 644 "${CERT_DIR}"/*.crt

echo "=== Certificados generados en ${CERT_DIR}/ ==="
ls -la "${CERT_DIR}/"

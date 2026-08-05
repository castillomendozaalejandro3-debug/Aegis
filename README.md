# Project Aegis-Peru

Sistema de Inteligencia OSINT (Open Source Intelligence) para investigacion criminal.
Plataforma de analisis forense digital con recoleccion automatizada de datos desde
fuentes publicas, procesamiento con IA (VLM/NER), y persistencia en grafo de
conocimiento.

## Arquitectura

```
┌─────────────┐     ┌─────────────┐     ┌─────────────────────────────────────┐
│   Nginx     │────▶│    Kong     │────▶│         Aegis Core API              │
│  (HTTPS)    │     │  (mTLS)     │     │  FastAPI + LangGraph + Playwright   │
└─────────────┘     └─────────────┘     └─────────────────────────────────────┘
                                                 │
                    ┌────────────┬───────────────┼───────────────┬────────────┐
                    ▼            ▼               ▼               ▼            ▼
               ┌────────┐  ┌─────────┐    ┌──────────┐   ┌──────────┐  ┌────────┐
               │Neo4j   │  │Qdrant   │    │PostgreSQL│   │Redis     │  │Tor     │
               │(Grafo) │  │(Vectors)│    │(Relacional)│  │(Cache)   │  │(Proxy) │
               └────────┘  └─────────┘    └──────────┘   └──────────┘  └────────┘
```

## Requisitos

- Docker 24.0+ y Docker Compose 2.20+
- 8GB RAM minimo (16GB recomendado)
- 50GB espacio en disco

## Instalacion Rapida

```bash
# 1. Clonar y entrar al directorio
cd aegis-peru

# 2. Generar certificados TLS
chmod +x generate-certs.sh
./generate-certs.sh

# 3. Configurar variables de entorno
cp .env.example .env
# Editar .env con valores reales

# 4. Iniciar servicios
docker-compose up -d

# 5. Verificar estado
docker-compose ps
curl -k https://localhost/health
```

## Servicios

| Servicio    | Puerto    | Descripcion                          |
|-------------|-----------|--------------------------------------|
| Kong        | 80/443    | API Gateway con rate limiting, JWT   |
| Core API    | 8000      | FastAPI - Pipeline OSINT             |
| Worker      | -         | Celery workers para scraping         |
| UI          | 8443      | React frontend                       |
| Neo4j       | 7474/7687 | Grafo de conocimiento                |
| PostgreSQL  | 5432      | Base de datos relacional             |
| Qdrant      | 6333      | Base de datos vectorial              |
| Redis       | 6379      | Cache y broker Celery                |
| Tor         | 9050/9051 | Proxy anonimo para dark web          |
| Vault       | 8200      | Gestion de secretos                  |
| Prometheus  | 9090      | Metricas                             |
| Grafana     | 3000      | Dashboards                           |

## Uso

### 1. Autenticacion
```bash
curl -X POST https://localhost/api/v1/auth/login   -d "username=admin"   -d "password=admin"
```

### 2. Ingesta de Evidencia
```bash
curl -X POST https://localhost/api/v1/ingest   -H "Authorization: Bearer <token>"   -F "investigation_id=INV-2026-001"   -F "image=@foto.jpg"   -F "dni_hint=12345678"
```

### 3. Consulta de Grafo
```bash
curl -X POST https://localhost/api/v1/query   -H "Authorization: Bearer <token>"   -d "cypher_query=MATCH (p:Person) RETURN p LIMIT 10"
```

## Scrapers Implementados

| Fuente        | Tipo      | Datos Extraidos                          |
|---------------|-----------|------------------------------------------|
| SUNAT         | Browser   | RUC, razon social, estado, direccion     |
| RENIEC/DNI    | HTTP      | Nombres, fecha nacimiento, sexo          |
| SUNEDU        | HTTP      | Grados academicos, universidad           |
| SUNARP        | HTTP      | Propiedades, vehiculos, titular          |
| HaveIBeenPwned| API       | Breaches de email                        |
| BreachDirectory| Scraping | Datos comprometidos                      |
| Intelligence X| Scraping  | Email, telefono en breaches              |
| Shodan        | API       | Hosts, puertos, servicios                |
| Censys        | API       | Infraestructura expuesta                 |

## Seguridad

- mTLS entre todos los servicios
- JWT con expiracion configurable
- Rate limiting por IP y usuario
- Proxy Tor para anonimato operacional
- Reglas Sigma para deteccion de fugas de IP
- Logging estructurado con request_id
- Contenedores read-only con no-new-privileges

## Licencia

Proyecto de uso exclusivo para instituciones de investigacion criminal autorizadas.

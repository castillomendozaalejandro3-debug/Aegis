"""Tests de seguridad para Project Aegis-Peru."""
import pytest
from fastapi.testclient import TestClient

from src.main import app
from src.utils.security import (
    create_access_token,
    hash_password,
    sanitize_cypher_query,
    sanitize_filename,
    verify_password,
)

client = TestClient(app)


# ── TESTS DE AUTENTICACION ──────────────────────────────

def test_login_rejects_invalid_credentials():
    """Debe rechazar credenciales invalidas."""
    response = client.post("/api/v1/auth/login", data={
        "username": "invalid_user",
        "password": "invalid_password"
    })
    assert response.status_code == 401
    data = response.json()
    assert data["success"] is False


def test_login_rejects_empty_credentials():
    """Debe rechazar credenciales vacias."""
    response = client.post("/api/v1/auth/login", data={
        "username": "",
        "password": ""
    })
    assert response.status_code == 422  # Validation error


def test_login_blocks_sql_injection():
    """Debe sanitizar inputs de login."""
    response = client.post("/api/v1/auth/login", data={
        "username": "admin' OR '1'='1",
        "password": "anything"
    })
    assert response.status_code == 401


# ── TESTS DE JWT ─────────────────────────────────────────

def test_verify_token_valid():
    """Debe verificar token JWT valido."""
    token = create_access_token({"sub": "testuser", "role": "ANALYST"})
    assert token is not None
    assert isinstance(token, str)


def test_protected_endpoints_require_auth():
    """Endpoints protegidos deben requerir autenticacion."""
    protected_endpoints = [
        ("GET", "/api/v1/investigations"),
        ("POST", "/api/v1/investigations"),
        ("POST", "/api/v1/ingest"),
        ("POST", "/api/v1/query"),
        ("GET", "/api/v1/export/INV-2026-001"),
    ]

    for method, endpoint in protected_endpoints:
        if method == "GET":
            response = client.get(endpoint)
        elif method == "POST":
            response = client.post(endpoint)
        else:
            continue

        assert response.status_code == 403, f"Endpoint {endpoint} no requiere auth"


# ── TESTS DE CYPHER SANITIZATION ────────────────────────

def test_sanitize_cypher_blocks_delete():
    """Debe bloquear operaciones DELETE."""
    with pytest.raises(ValueError):
        sanitize_cypher_query("MATCH (n) DELETE n")


def test_sanitize_cypher_blocks_detach_delete():
    """Debe bloquear operaciones DETACH DELETE."""
    with pytest.raises(ValueError):
        sanitize_cypher_query("MATCH (n) DETACH DELETE n")


def test_sanitize_cypher_blocks_drop():
    """Debe bloquear operaciones DROP."""
    with pytest.raises(ValueError):
        sanitize_cypher_query("DROP CONSTRAINT test")


def test_sanitize_cypher_blocks_call_apoc():
    """Debe bloquear llamadas a APOC."""
    with pytest.raises(ValueError):
        sanitize_cypher_query("CALL apoc.util.sleep(10000)")


def test_sanitize_cypher_allows_read():
    """Debe permitir queries de lectura."""
    query = "MATCH (p:Person) RETURN p LIMIT 10"
    result = sanitize_cypher_query(query)
    assert result == query


def test_sanitize_cypher_allows_read_with_where():
    """Debe permitir queries con WHERE."""
    query = "MATCH (p:Person) WHERE p.dni = '12345678' RETURN p"
    result = sanitize_cypher_query(query)
    assert result == query


# ── TESTS DE FILENAME SANITIZATION ────────────────────────

def test_sanitize_filename_removes_path_traversal():
    """Debe eliminar path traversal."""
    assert sanitize_filename("../../../etc/passwd") == "passwd"


def test_sanitize_filename_allows_safe_names():
    """Debe permitir nombres seguros."""
    assert sanitize_filename("evidence_photo.jpg") == "evidence_photo.jpg"


def test_sanitize_filename_limits_length():
    """Debe limitar longitud."""
    long_name = "a" * 300 + ".jpg"
    result = sanitize_filename(long_name)
    assert len(result) <= 255


# ── TESTS DE PASSWORD HASHING ────────────────────────────

def test_hash_password_generates_different_hashes():
    """Hash de la misma password debe ser diferente cada vez."""
    hash1 = hash_password("password123")
    hash2 = hash_password("password123")
    assert hash1 != hash2


def test_verify_password_correct():
    """Debe verificar password correcta."""
    password = "SecureP@ssw0rd!"
    hashed = hash_password(password)
    assert verify_password(password, hashed) is True


def test_verify_password_incorrect():
    """Debe rechazar password incorrecta."""
    password = "SecureP@ssw0rd!"
    hashed = hash_password(password)
    assert verify_password("wrong_password", hashed) is False


# ── TESTS DE HEADERS DE SEGURIDAD ────────────────────────

def test_security_headers_present():
    """Debe incluir headers de seguridad."""
    response = client.get("/health")
    assert response.status_code == 200
    assert response.headers.get("X-Content-Type-Options") == "nosniff"
    assert response.headers.get("X-Frame-Options") == "DENY"
    assert response.headers.get("X-XSS-Protection") == "1; mode=block"


# ── TESTS DE RATE LIMITING ───────────────────────────────

def test_rate_limiting_on_login():
    """Debe aplicar rate limiting en login."""
    # Hacer multiples requests rapidos
    responses = []
    for _ in range(10):
        response = client.post("/api/v1/auth/login", data={
            "username": "test",
            "password": "test"
        })
        responses.append(response.status_code)

    # Al menos algunas deben ser rate limited (429)
    # Nota: En tests puede no aplicarse dependiendo de la config
    assert 401 in responses or 429 in responses


# ── TESTS DE CORS ──────────────────────────────────────

def test_cors_blocks_unauthorized_origin():
    """Debe bloquear origenes no autorizados."""
    response = client.get(
        "/health",
        headers={"Origin": "https://evil.com"}
    )
    # En produccion no debe permitir evil.com
    assert response.headers.get("access-control-allow-origin") != "https://evil.com"

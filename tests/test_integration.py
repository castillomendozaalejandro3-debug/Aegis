"""Tests de integracion para Project Aegis-Peru."""
import pytest
from fastapi.testclient import TestClient

from src.main import app
from src.utils.crypto import generate_sha256
from src.utils.security import create_access_token
from src.models.schemas import Role

client = TestClient(app)


def test_imports():
    """Verifica que todos los modulos se importan correctamente."""
    from src.config.settings import get_settings
    from src.models.schemas import InvestigationSchema, IngestPayload
    from src.utils.crypto import generate_sha256
    from src.utils.logger import get_logger
    assert get_settings() is not None


def test_dni_validation():
    """Valida algoritmo de verificacion DNI."""
    from src.tools.base_scraper import validate_dni
    assert validate_dni("12345678") is True
    assert validate_dni("1234567") is False
    assert validate_dni("123456789") is False
    assert validate_dni("abcdefgh") is False


def test_ruc_validation():
    """Valida formato de RUC."""
    from src.tools.base_scraper import validate_ruc
    assert validate_ruc("12345678901") is True
    assert validate_ruc("1234567890") is False
    assert validate_ruc("123456789012") is False


def test_email_validation():
    """Valida formato de email."""
    from src.tools.base_scraper import validate_email
    assert validate_email("test@example.com") is True
    assert validate_email("invalid") is False


def test_phone_validation():
    """Valida formato de telefono peruano."""
    from src.tools.base_scraper import validate_phone_peru
    assert validate_phone_peru("+51987654321") is True
    assert validate_phone_peru("987654321") is True
    assert validate_phone_peru("123456") is False


def test_crypto_hash():
    """Prueba funciones criptograficas."""
    from src.utils.crypto import generate_sha256
    hash1 = generate_sha256(b"test")
    hash2 = generate_sha256(b"test")
    assert hash1 == hash2
    assert len(hash1) == 64


@pytest.mark.asyncio
async def test_health_endpoint():
    """Prueba endpoint de health check."""
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] in ["healthy", "degraded"]
    assert "services" in data


def test_health_ready_endpoint():
    """Prueba endpoint de readiness."""
    response = client.get("/health/ready")
    # Puede ser 200 o 503 dependiendo del estado de la DB
    assert response.status_code in [200, 503]


def test_docs_disabled_in_production():
    """Documentacion debe estar deshabilitada en produccion."""
    from src.config.settings import settings
    if settings.environment == "production":
        response = client.get("/docs")
        assert response.status_code == 404


def test_create_access_token():
    """Prueba creacion de token JWT."""
    token = create_access_token({"sub": "test", "role": Role.ANALYST.value})
    assert token is not None
    assert isinstance(token, str)
    assert "." in token  # Formato JWT


def test_security_headers():
    """Verifica headers de seguridad en respuestas."""
    response = client.get("/health")
    assert response.status_code == 200
    assert response.headers.get("X-Content-Type-Options") == "nosniff"
    assert response.headers.get("X-Frame-Options") == "DENY"
    assert response.headers.get("X-XSS-Protection") == "1; mode=block"
    assert "X-Request-ID" in response.headers


def test_request_id_propagation():
    """Verifica propagacion de request ID."""
    custom_id = "test-request-id-123"
    response = client.get("/health", headers={"X-Request-ID": custom_id})
    assert response.headers.get("X-Request-ID") == custom_id

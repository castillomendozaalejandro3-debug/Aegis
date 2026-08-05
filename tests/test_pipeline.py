"""Tests del pipeline LangGraph y nodos."""
import pytest

from src.nodes.collect_data import collect_data_node
from src.nodes.analyze_extract import analyze_extract_node
from src.nodes.persist_graph import persist_graph_node
from src.models.schemas import IngestPayload


# ── TESTS DE COLLECT DATA NODE ───────────────────────────

def test_collect_data_empty_payload():
    """Debe manejar payload vacio sin errores."""
    state = {
        "payload": {},
        "investigation_id": "INV-2026-001",
        "stage": "collect_data",
        "retry_count": 0,
        "error": None,
    }
    result = collect_data_node(state)
    assert result["error"] is None
    assert result["stage"] == "collect_data"
    assert "collected_data" in result


def test_collect_data_with_dni_hint():
    """Debe procesar hint de DNI."""
    payload = IngestPayload(
        investigation_id="INV-2026-001",
        dni_hint="12345678",
    )
    state = {
        "payload": payload,
        "investigation_id": "INV-2026-001",
        "stage": "collect_data",
        "retry_count": 0,
        "error": None,
    }
    result = collect_data_node(state)
    assert result["error"] is None
    assert "collected_data" in result


def test_collect_data_with_ruc_hint():
    """Debe procesar hint de RUC."""
    payload = IngestPayload(
        investigation_id="INV-2026-001",
        ruc_hint="12345678901",
    )
    state = {
        "payload": payload,
        "investigation_id": "INV-2026-001",
        "stage": "collect_data",
        "retry_count": 0,
        "error": None,
    }
    result = collect_data_node(state)
    assert result["error"] is None


def test_collect_data_with_text_query():
    """Debe procesar consulta de texto."""
    payload = IngestPayload(
        investigation_id="INV-2026-001",
        text_query="Juan Perez Lima",
    )
    state = {
        "payload": payload,
        "investigation_id": "INV-2026-001",
        "stage": "collect_data",
        "retry_count": 0,
        "error": None,
    }
    result = collect_data_node(state)
    assert result["error"] is None
    assert result["collected_data"]["raw_data"].get("text_query") == "Juan Perez Lima"


# ── TESTS DE ANALYZE EXTRACT NODE ──────────────────────

def test_analyze_extract_empty_collected():
    """Debe manejar datos recolectados vacios."""
    state = {
        "collected_data": {
            "dni_results": [],
            "sunat_results": [],
            "raw_data": {},
        },
        "investigation_id": "INV-2026-001",
        "stage": "analyze_extract",
        "error": None,
    }
    result = analyze_extract_node(state)
    assert result["error"] is None
    assert result["stage"] == "analyze_extract"
    assert "analysis_result" in result
    assert result["analysis_result"]["confidence_aggregate"] == 0.0


def test_analyze_extract_with_dni_result():
    """Debe extraer persona desde resultado DNI."""
    state = {
        "collected_data": {
            "dni_results": [
                {
                    "dni": "12345678",
                    "full_name": "Juan Carlos Perez Garcia",
                    "nombres": "Juan Carlos",
                    "apellido_paterno": "Perez",
                    "apellido_materno": "Garcia",
                    "fecha_nacimiento": "1990-01-15",
                    "sexo": "M",
                    "source": "RENIEC",
                    "confidence": 0.95,
                }
            ],
            "sunat_results": [],
            "raw_data": {},
        },
        "investigation_id": "INV-2026-001",
        "stage": "analyze_extract",
        "error": None,
    }
    result = analyze_extract_node(state)
    assert result["error"] is None
    assert len(result["analysis_result"]["persons"]) == 1
    assert result["analysis_result"]["persons"][0]["dni"] == "12345678"
    assert result["analysis_result"]["confidence_aggregate"] > 0


def test_analyze_extract_with_image():
    """Debe procesar imagen y generar asset."""
    state = {
        "collected_data": {
            "dni_results": [],
            "sunat_results": [],
            "raw_data": {
                "has_image": True,
                "image_filename": "evidence.jpg",
            },
        },
        "payload": {
            "image_bytes": b"fake_image_data",
            "image_filename": "evidence.jpg",
        },
        "investigation_id": "INV-2026-001",
        "stage": "analyze_extract",
        "error": None,
    }
    result = analyze_extract_node(state)
    assert result["error"] is None
    assert len(result["analysis_result"]["assets"]) == 1
    assert result["analysis_result"]["assets"][0]["asset_type"] == "IMAGE"


def test_analyze_extract_with_contacts():
    """Debe extraer contactos desde hints."""
    state = {
        "collected_data": {
            "dni_results": [],
            "sunat_results": [],
            "raw_data": {
                "phone_hint": "+51987654321",
                "email_hint": "test@example.com",
            },
        },
        "investigation_id": "INV-2026-001",
        "stage": "analyze_extract",
        "error": None,
    }
    result = analyze_extract_node(state)
    assert result["error"] is None
    contacts = result["analysis_result"]["contacts"]
    assert len(contacts) == 2
    assert contacts[0]["contact_type"] == "PHONE"
    assert contacts[1]["contact_type"] == "EMAIL"


# ── TESTS DE PERSIST GRAPH NODE ──────────────────────────

def test_persist_graph_no_data():
    """Debe manejar falta de datos de analisis."""
    state = {
        "analysis_result": {},
        "investigation_id": "INV-2026-001",
        "stage": "persist_graph",
        "error": None,
    }
    result = persist_graph_node(state)
    assert result["error"] is not None
    assert result["stage"] == "persist_failed"


# ── TESTS DE INTEGRACION ─────────────────────────────────

def test_full_pipeline_mock():
    """Test de integracion del pipeline completo (mock)."""
    from src.orchestrator import run_pipeline

    payload = IngestPayload(
        investigation_id="INV-2026-001",
        text_query="Test investigation",
        dni_hint="12345678",
    )

    # Nota: Este test puede fallar si Neo4j no esta disponible
    # En un entorno de CI/CD se usarian mocks
    result = run_pipeline(payload, "INV-2026-001")

    assert "pipeline_status" in result
    assert result["investigation_id"] == "INV-2026-001"
    assert "processing_time_seconds" in result

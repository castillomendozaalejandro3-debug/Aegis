"""Nodo de analisis y extraccion de entidades - NER, VLM, correlacion."""
import uuid
from datetime import datetime
from typing import Any, Dict, List

from src.models.schemas import (
    AnalysisResult,
    AssetSchema,
    AssetType,
    ContactSchema,
    ContactType,
    DigitalFootprintSchema,
    LocationSchema,
    PersonSchema,
)
from src.utils.crypto import generate_sha256
from src.utils.logger import get_logger

logger = get_logger("aegis.node.analyze")


def analyze_extract_node(state: Dict[str, Any]) -> Dict[str, Any]:
    """Nodo LangGraph: Analiza datos recolectados y extrae entidades.

    Args:
        state: Estado actual con datos recolectados

    Returns:
        Estado actualizado con entidades extraidas
    """
    logger.info("analyze_extract_start")
    collected = state.get("collected_data", {})
    investigation_id = state.get("investigation_id", "")
    raw_data = collected.get("raw_data", {})

    analysis = {
        "extracted_entities": {},
        "persons": [],
        "contacts": [],
        "locations": [],
        "assets": [],
        "darkweb_profiles": [],
        "digital_footprints": [],
        "sunat_results": [],
        "dni_results": [],
        "sunedu_results": [],
        "sunarp_results": [],
        "breach_results": [],
        "confidence_aggregate": 0.0,
        "processing_metadata": {
            "stage": "analyze_extract",
            "timestamp": datetime.utcnow().isoformat(),
        },
        "threat_indicators": [],
    }

    confidence_scores = []

    # ── PROCESAR RESULTADOS DNI ──────────────────────────
    for dni_data in collected.get("dni_results", []):
        try:
            person = {
                "uuid": str(uuid.uuid4()),
                "dni": dni_data.get("dni"),
                "full_name": dni_data.get("full_name") or _build_full_name(dni_data),
                "alias": [],
                "date_of_birth": dni_data.get("fecha_nacimiento"),
                "nationality": "Peruana",
                "gender": dni_data.get("sexo"),
                "risk_score": 0.0,
                "status": "ACTIVE",
                "source": dni_data.get("source", "RENIEC"),
                "confidence": dni_data.get("confidence", 0.9),
                "investigation_id": investigation_id,
            }
            analysis["persons"].append(person)
            analysis["dni_results"].append(dni_data)
            confidence_scores.append(person["confidence"])
            logger.info("person_extracted_from_dni", dni=person["dni"])
        except Exception as e:
            logger.warning("dni_analysis_failed", error=str(e))

    # ── PROCESAR RESULTADOS SUNAT ─────────────────────────
    for sunat_data in collected.get("sunat_results", []):
        try:
            analysis["sunat_results"].append(sunat_data)
            confidence_scores.append(sunat_data.get("confidence", 0.95))

            # Crear persona juridica si no existe persona natural
            if sunat_data.get("tipo_persona") == "JURIDICA":
                person = {
                    "uuid": str(uuid.uuid4()),
                    "dni": None,
                    "full_name": sunat_data.get("razon_social"),
                    "alias": [],
                    "nationality": "Peruana",
                    "risk_score": 0.0,
                    "status": "ACTIVE",
                    "source": "SUNAT",
                    "confidence": sunat_data.get("confidence", 0.95),
                    "investigation_id": investigation_id,
                }
                analysis["persons"].append(person)
                logger.info("person_extracted_from_sunat", ruc=sunat_data.get("ruc"))
        except Exception as e:
            logger.warning("sunat_analysis_failed", error=str(e))

    # ── PROCESAR IMAGEN ───────────────────────────────────
    if raw_data.get("has_image"):
        try:
            image_bytes = state.get("payload", {}).get("image_bytes")
            image_filename = raw_data.get("image_filename", "unknown")

            if image_bytes:
                file_hash = generate_sha256(image_bytes)
                asset = {
                    "uuid": str(uuid.uuid4()),
                    "asset_type": AssetType.IMAGE.value,
                    "hash": file_hash,
                    "filename": image_filename,
                    "mime_type": _detect_mime_type(image_filename),
                    "size_bytes": len(image_bytes),
                    "exif_data": {},  # TODO: Extraer EXIF
                    "storage_path": f"/app/evidence/{investigation_id}/{file_hash[:16]}",
                    "source": "OPERATOR_UPLOAD",
                    "confidence": 1.0,
                    "investigation_id": investigation_id,
                }
                analysis["assets"].append(asset)
                confidence_scores.append(1.0)
                logger.info("asset_extracted", hash=file_hash[:16])

                # TODO: Integrar VLM para analisis de imagen
                # TODO: Extraer texto con OCR
                # TODO: Detectar rostros, vehiculos, placas
        except Exception as e:
            logger.warning("image_analysis_failed", error=str(e))

    # ── PROCESAR CONTACTOS DESDE HINTS ─────────────────────
    phone_hint = raw_data.get("phone_hint")
    if phone_hint:
        contact = {
            "uuid": str(uuid.uuid4()),
            "contact_type": ContactType.PHONE.value,
            "value": phone_hint,
            "carrier": None,
            "domain": None,
            "is_verified": False,
            "source": "OPERATOR_INPUT",
            "confidence": 0.8,
            "investigation_id": investigation_id,
        }
        analysis["contacts"].append(contact)
        confidence_scores.append(0.8)

    email_hint = raw_data.get("email_hint")
    if email_hint:
        contact = {
            "uuid": str(uuid.uuid4()),
            "contact_type": ContactType.EMAIL.value,
            "value": email_hint,
            "domain": email_hint.split("@")[-1] if "@" in email_hint else None,
            "is_verified": False,
            "source": "OPERATOR_INPUT",
            "confidence": 0.85,
            "investigation_id": investigation_id,
        }
        analysis["contacts"].append(contact)
        confidence_scores.append(0.85)

    # ── PROCESAR ALIAS ────────────────────────────────────
    alias_hint = raw_data.get("alias_hint")
    if alias_hint and analysis["persons"]:
        # Agregar alias a la primera persona encontrada
        analysis["persons"][0]["alias"].append(alias_hint)
        logger.info("alias_linked", alias=alias_hint)

    # ── CALCULAR CONFIANZA AGREGADA ────────────────────────
    if confidence_scores:
        analysis["confidence_aggregate"] = round(
            sum(confidence_scores) / len(confidence_scores), 4
        )

    # ── INDICADORES DE AMENAZA ───────────────────────────
    if analysis["breach_results"]:
        analysis["threat_indicators"].append("BREACH_DATA_DETECTED")
    if len(analysis["persons"]) > 1:
        analysis["threat_indicators"].append("MULTIPLE_IDENTITIES")

    state["analysis_result"] = analysis
    state["stage"] = "analyze_extract"
    state["error"] = None

    logger.info(
        "analyze_extract_complete",
        persons=len(analysis["persons"]),
        contacts=len(analysis["contacts"]),
        assets=len(analysis["assets"]),
        confidence=analysis["confidence_aggregate"],
    )
    return state


def _build_full_name(dni_data: Dict[str, Any]) -> str:
    """Construye nombre completo desde partes del DNI."""
    parts = []
    if dni_data.get("apellido_paterno"):
        parts.append(dni_data["apellido_paterno"])
    if dni_data.get("apellido_materno"):
        parts.append(dni_data["apellido_materno"])
    if dni_data.get("nombres"):
        parts.append(dni_data["nombres"])
    return " ".join(parts) if parts else "DESCONOCIDO"


def _detect_mime_type(filename: str) -> str:
    """Detecta MIME type desde extension de archivo."""
    ext = filename.lower().split(".")[-1] if "." in filename else ""
    mime_map = {
        "jpg": "image/jpeg",
        "jpeg": "image/jpeg",
        "png": "image/png",
        "webp": "image/webp",
        "tiff": "image/tiff",
        "tif": "image/tiff",
    }
    return mime_map.get(ext, "application/octet-stream")

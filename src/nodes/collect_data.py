"""Nodo de recoleccion de datos OSINT - Fuentes publicas peruanas."""
import uuid
from typing import Any, Dict, List, Optional

from src.models.schemas import DniResult, SunatResult
from src.tools.dni_scraper import query_dni
from src.tools.sunat_scraper import query_sunat_ruc
from src.utils.logger import get_logger

logger = get_logger("aegis.node.collect")


def collect_data_node(state: Dict[str, Any]) -> Dict[str, Any]:
    """Nodo LangGraph: Recolecta datos desde fuentes OSINT.

    Args:
        state: Estado actual del pipeline con payload de ingesta

    Returns:
        Estado actualizado con datos recolectados
    """
    logger.info("collect_data_start")
    payload = state.get("payload", {})

    collected = {
        "dni_results": [],
        "sunat_results": [],
        "sunedu_results": [],
        "sunarp_results": [],
        "breach_results": [],
        "digital_footprints": [],
        "raw_data": {},
    }

    # ── CONSULTA DNI ──────────────────────────────────────
    dni_hint = getattr(payload, "dni_hint", None) or payload.get("dni_hint")
    if dni_hint:
        try:
            logger.info("collecting_dni", dni=dni_hint)
            result = query_dni(dni_hint)
            if result:
                collected["dni_results"].append(result.model_dump())
                logger.info("dni_collection_success", dni=dni_hint)
        except Exception as e:
            logger.warning("dni_collection_failed", dni=dni_hint, error=str(e))
            # No fallar el pipeline por un scraper individual

    # ── CONSULTA RUC/SUNAT ─────────────────────────────────
    ruc_hint = getattr(payload, "ruc_hint", None) or payload.get("ruc_hint")
    if ruc_hint:
        try:
            logger.info("collecting_ruc", ruc=ruc_hint)
            result = query_sunat_ruc(ruc_hint)
            if result:
                collected["sunat_results"].append(result.model_dump())
                logger.info("sunat_collection_success", ruc=ruc_hint)
        except Exception as e:
            logger.warning("sunat_collection_failed", ruc=ruc_hint, error=str(e))

    # ── CONSULTA POR NOMBRE (si hay text_query) ────────────
    text_query = getattr(payload, "text_query", None) or payload.get("text_query")
    if text_query and len(text_query) >= 3:
        logger.info("text_query_detected", query=text_query[:50])
        # TODO: Integrar busqueda por nombre en SUNAT
        # TODO: Integrar busqueda en fuentes OSINT externas
        collected["raw_data"]["text_query"] = text_query

    # ── ALIAS / TELEFONO / EMAIL ──────────────────────────
    alias_hint = getattr(payload, "alias_hint", None) or payload.get("alias_hint")
    phone_hint = getattr(payload, "phone_hint", None) or payload.get("phone_hint")
    email_hint = getattr(payload, "email_hint", None) or payload.get("email_hint")

    if alias_hint:
        collected["raw_data"]["alias_hint"] = alias_hint
    if phone_hint:
        collected["raw_data"]["phone_hint"] = phone_hint
    if email_hint:
        collected["raw_data"]["email_hint"] = email_hint

    # ── IMAGEN ────────────────────────────────────────────
    image_bytes = getattr(payload, "image_bytes", None) or payload.get("image_bytes")
    image_filename = getattr(payload, "image_filename", None) or payload.get("image_filename")
    if image_bytes:
        collected["raw_data"]["has_image"] = True
        collected["raw_data"]["image_filename"] = image_filename
        # TODO: Extraer EXIF, hash, metadatos
        logger.info("image_detected", filename=image_filename)

    state["collected_data"] = collected
    state["stage"] = "collect_data"
    state["error"] = None

    logger.info(
        "collect_data_complete",
        dni_results=len(collected["dni_results"]),
        sunat_results=len(collected["sunat_results"]),
    )
    return state

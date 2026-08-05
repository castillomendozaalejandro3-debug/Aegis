"""Logging estructurado con request_id propagation - structlog."""
import logging
import sys
import uuid
from contextvars import ContextVar
from typing import Any, Dict, Optional

import structlog
from structlog.processors import JSONRenderer, TimeStamper, add_log_level
from structlog.stdlib import BoundLogger, LoggerFactory

from src.config.settings import settings

# ContextVar para propagar request_id entre async tasks
request_id_var: ContextVar[str] = ContextVar("request_id", default="system")


def _add_request_id(logger: Any, method_name: str, event_dict: Dict[str, Any]) -> Dict[str, Any]:
    """Processor que anade request_id desde ContextVar."""
    event_dict["request_id"] = request_id_var.get()
    return event_dict


def _add_service_info(logger: Any, method_name: str, event_dict: Dict[str, Any]) -> Dict[str, Any]:
    """Processor que anade info del servicio."""
    event_dict["service"] = "aegis-peru"
    event_dict["version"] = "1.0.0"
    event_dict["environment"] = "production"
    return event_dict


def configure_logging() -> None:
    """Configura structlog con processors de produccion."""
    shared_processors: list = [
        structlog.contextvars.merge_contextvars,
        add_log_level,
        TimeStamper(fmt="iso", utc=True),
        _add_request_id,
        _add_service_info,
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
    ]

    if settings.json_logs:
        renderer = JSONRenderer()
    else:
        renderer = structlog.dev.ConsoleRenderer(colors=True)

    structlog.configure(
        processors=shared_processors + [renderer],
        context_class=dict,
        logger_factory=LoggerFactory(),
        wrapper_class=BoundLogger,
        cache_logger_on_first_use=True,
    )

    # Configurar logging estandar para que use structlog
    logging.basicConfig(
        format="%(message)s",
        stream=sys.stdout,
        level=getattr(logging, settings.log_level),
    )


def get_logger(name: str) -> BoundLogger:
    """Obtiene un logger estructurado con el nombre del modulo."""
    return structlog.get_logger(name)


def set_request_id(request_id: Optional[str] = None) -> str:
    """Establece o genera un request_id en el contexto actual."""
    rid = request_id or str(uuid.uuid4())
    request_id_var.set(rid)
    return rid


def get_request_id() -> str:
    """Obtiene el request_id actual del contexto."""
    return request_id_var.get()


# Configurar al importar
configure_logging()

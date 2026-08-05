"""Sistema de alertas en tiempo real - WebSocket + SSE.

Supera a sistemas tradicionales al usar:
- WebSocket bidireccional para actualizaciones instantaneas
- Server-Sent Events para broadcast eficiente
- Filtros de alertas por usuario/rol
- Escalacion automatica basada en severidad
- Integracion con Telegram/Slack/Email
"""
import asyncio
import json
from collections import deque
from datetime import datetime, timedelta
from typing import Any, Callable, Dict, List, Optional, Set

from fastapi import WebSocket, WebSocketDisconnect

from src.config.settings import settings
from src.models.schemas import Role
from src.utils.logger import get_logger

logger = get_logger("aegis.alert_system")


class Alert:
    """Modelo de alerta estandarizado."""

    SEVERITY_LEVELS = {
        "INFO": 1,
        "LOW": 2,
        "MEDIUM": 3,
        "HIGH": 4,
        "CRITICAL": 5,
    }

    def __init__(
        self,
        alert_type: str,
        severity: str,
        title: str,
        message: str,
        source: str,
        investigation_id: Optional[str] = None,
        entity_id: Optional[str] = None,
        metadata: Optional[Dict] = None,
        ttl_seconds: int = 86400,  # 24 horas
    ):
        self.id = f"ALERT-{datetime.utcnow().strftime('%Y%m%d%H%M%S')}-{hash(message) % 10000:04d}"
        self.alert_type = alert_type
        self.severity = severity.upper()
        self.title = title
        self.message = message
        self.source = source
        self.investigation_id = investigation_id
        self.entity_id = entity_id
        self.metadata = metadata or {}
        self.created_at = datetime.utcnow()
        self.expires_at = self.created_at + timedelta(seconds=ttl_seconds)
        self.acknowledged_by: Optional[str] = None
        self.acknowledged_at: Optional[datetime] = None

    def to_dict(self) -> Dict:
        return {
            "id": self.id,
            "alert_type": self.alert_type,
            "severity": self.severity,
            "severity_level": self.SEVERITY_LEVELS.get(self.severity, 1),
            "title": self.title,
            "message": self.message,
            "source": self.source,
            "investigation_id": self.investigation_id,
            "entity_id": self.entity_id,
            "metadata": self.metadata,
            "created_at": self.created_at.isoformat(),
            "expires_at": self.expires_at.isoformat(),
            "acknowledged_by": self.acknowledged_by,
            "acknowledged_at": self.acknowledged_at.isoformat() if self.acknowledged_at else None,
        }

    def is_expired(self) -> bool:
        return datetime.utcnow() > self.expires_at

    def is_acknowledged(self) -> bool:
        return self.acknowledged_by is not None


class AlertFilter:
    """Filtro configurable de alertas."""

    def __init__(
        self,
        min_severity: Optional[str] = None,
        alert_types: Optional[List[str]] = None,
        sources: Optional[List[str]] = None,
        investigation_ids: Optional[List[str]] = None,
        roles: Optional[List[Role]] = None,
    ):
        self.min_severity = min_severity
        self.alert_types = set(alert_types or [])
        self.sources = set(sources or [])
        self.investigation_ids = set(investigation_ids or [])
        self.roles = set(roles or [])

    def matches(self, alert: Alert, user_role: Optional[str] = None) -> bool:
        """Verifica si una alerta pasa el filtro."""
        # Verificar severidad minima
        if self.min_severity:
            if Alert.SEVERITY_LEVELS.get(alert.severity, 0) < Alert.SEVERITY_LEVELS.get(self.min_severity, 0):
                return False

        # Verificar tipo
        if self.alert_types and alert.alert_type not in self.alert_types:
            return False

        # Verificar fuente
        if self.sources and alert.source not in self.sources:
            return False

        # Verificar investigacion
        if self.investigation_ids and alert.investigation_id not in self.investigation_ids:
            return False

        # Verificar rol
        if self.roles and user_role not in [r.value for r in self.roles]:
            return False

        return True


class AlertManager:
    """Gestor central de alertas.
    
    Implementa patron Observer para notificaciones en tiempo real.
    """

    def __init__(self, max_history: int = 10000):
        self.alerts: deque = deque(maxlen=max_history)
        self.active_alerts: Dict[str, Alert] = {}
        self.websocket_clients: Dict[str, List[WebSocket]] = {}
        self.sse_clients: Dict[str, List[asyncio.Queue]] = {}
        self.filters: Dict[str, AlertFilter] = {}
        self.external_handlers: List[Callable] = []
        self._cleanup_task: Optional[asyncio.Task] = None

    async def start(self):
        """Inicia el gestor de alertas."""
        self._cleanup_task = asyncio.create_task(self._cleanup_expired())
        logger.info("alert_manager_started")

    async def stop(self):
        """Detiene el gestor de alertas."""
        if self._cleanup_task:
            self._cleanup_task.cancel()
            try:
                await self._cleanup_task
            except asyncio.CancelledError:
                pass
        logger.info("alert_manager_stopped")

    async def create_alert(
        self,
        alert_type: str,
        severity: str,
        title: str,
        message: str,
        source: str,
        investigation_id: Optional[str] = None,
        entity_id: Optional[str] = None,
        metadata: Optional[Dict] = None,
    ) -> Alert:
        """Crea y distribuye una nueva alerta."""
        alert = Alert(
            alert_type=alert_type,
            severity=severity,
            title=title,
            message=message,
            source=source,
            investigation_id=investigation_id,
            entity_id=entity_id,
            metadata=metadata,
        )

        self.alerts.append(alert)
        self.active_alerts[alert.id] = alert

        logger.info(
            "alert_created",
            alert_id=alert.id,
            severity=alert.severity,
            type=alert.alert_type,
            investigation=investigation_id,
        )

        # Distribuir a clientes
        await self._distribute_alert(alert)

        # Notificar handlers externos
        await self._notify_external_handlers(alert)

        # Escalacion automatica para criticas
        if alert.severity == "CRITICAL":
            await self._escalate_critical(alert)

        return alert

    async def acknowledge_alert(self, alert_id: str, user_id: str) -> bool:
        """Marca una alerta como reconocida."""
        alert = self.active_alerts.get(alert_id)
        if not alert:
            return False

        alert.acknowledged_by = user_id
        alert.acknowledged_at = datetime.utcnow()

        logger.info("alert_acknowledged", alert_id=alert_id, user_id=user_id)

        # Notificar a todos los clientes
        await self._broadcast({
            "event": "alert_acknowledged",
            "alert_id": alert_id,
            "acknowledged_by": user_id,
            "timestamp": datetime.utcnow().isoformat(),
        })

        return True

    async def dismiss_alert(self, alert_id: str, user_id: str) -> bool:
        """Descarta una alerta."""
        if alert_id in self.active_alerts:
            del self.active_alerts[alert_id]
            logger.info("alert_dismissed", alert_id=alert_id, user_id=user_id)
            return True
        return False

    def get_active_alerts(
        self,
        filter_obj: Optional[AlertFilter] = None,
        user_role: Optional[str] = None,
    ) -> List[Dict]:
        """Obtiene alertas activas filtradas."""
        alerts = list(self.active_alerts.values())
        
        if filter_obj:
            alerts = [a for a in alerts if filter_obj.matches(a, user_role)]
        
        # Ordenar por severidad y fecha
        alerts.sort(key=lambda a: (-Alert.SEVERITY_LEVELS.get(a.severity, 0), a.created_at), reverse=False)
        
        return [a.to_dict() for a in alerts]

    def get_alert_history(
        self,
        hours: int = 24,
        filter_obj: Optional[AlertFilter] = None,
        user_role: Optional[str] = None,
    ) -> List[Dict]:
        """Obtiene historial de alertas."""
        cutoff = datetime.utcnow() - timedelta(hours=hours)
        alerts = [a for a in self.alerts if a.created_at > cutoff]
        
        if filter_obj:
            alerts = [a for a in alerts if filter_obj.matches(a, user_role)]
        
        alerts.sort(key=lambda a: a.created_at, reverse=True)
        return [a.to_dict() for a in alerts]

    # ── WEBSOCKET ───────────────────────────────────────────────────────

    async def register_websocket(self, client_id: str, websocket: WebSocket, filter_obj: Optional[AlertFilter] = None):
        """Registra un cliente WebSocket."""
        if client_id not in self.websocket_clients:
            self.websocket_clients[client_id] = []
        self.websocket_clients[client_id].append(websocket)
        
        if filter_obj:
            self.filters[client_id] = filter_obj

        logger.info("websocket_client_registered", client_id=client_id)

    async def unregister_websocket(self, client_id: str, websocket: WebSocket):
        """Desregistra un cliente WebSocket."""
        if client_id in self.websocket_clients:
            self.websocket_clients[client_id] = [w for w in self.websocket_clients[client_id] if w != websocket]
            if not self.websocket_clients[client_id]:
                del self.websocket_clients[client_id]
                self.filters.pop(client_id, None)

    # ── SSE ──────────────────────────────────────────────────────────────

    async def register_sse(self, client_id: str, queue: asyncio.Queue, filter_obj: Optional[AlertFilter] = None):
        """Registra un cliente SSE."""
        if client_id not in self.sse_clients:
            self.sse_clients[client_id] = []
        self.sse_clients[client_id].append(queue)
        
        if filter_obj:
            self.filters[client_id] = filter_obj

    async def unregister_sse(self, client_id: str, queue: asyncio.Queue):
        """Desregistra un cliente SSE."""
        if client_id in self.sse_clients:
            self.sse_clients[client_id] = [q for q in self.sse_clients[client_id] if q != queue]
            if not self.sse_clients[client_id]:
                del self.sse_clients[client_id]
                self.filters.pop(client_id, None)

    # ── DISTRIBUCION ────────────────────────────────────────────────────

    async def _distribute_alert(self, alert: Alert):
        """Distribuye alerta a todos los clientes conectados."""
        message = {
            "event": "new_alert",
            "data": alert.to_dict(),
        }

        # WebSocket
        for client_id, websockets in list(self.websocket_clients.items()):
            filter_obj = self.filters.get(client_id)
            if filter_obj and not filter_obj.matches(alert):
                continue

            for ws in websockets:
                try:
                    await ws.send_json(message)
                except Exception:
                    pass

        # SSE
        for client_id, queues in list(self.sse_clients.items()):
            filter_obj = self.filters.get(client_id)
            if filter_obj and not filter_obj.matches(alert):
                continue

            for queue in queues:
                try:
                    await queue.put(message)
                except Exception:
                    pass

    async def _broadcast(self, message: Dict):
        """Broadcast a todos los clientes."""
        # WebSocket
        for websockets in self.websocket_clients.values():
            for ws in websockets:
                try:
                    await ws.send_json(message)
                except Exception:
                    pass

        # SSE
        for queues in self.sse_clients.values():
            for queue in queues:
                try:
                    await queue.put(message)
                except Exception:
                    pass

    # ── HANDLERS EXTERNOS ───────────────────────────────────────────────

    def register_external_handler(self, handler: Callable):
        """Registra un handler para notificaciones externas."""
        self.external_handlers.append(handler)

    async def _notify_external_handlers(self, alert: Alert):
        """Notifica a handlers externos (Telegram, Slack, Email)."""
        for handler in self.external_handlers:
            try:
                await handler(alert)
            except Exception as e:
                logger.error("external_handler_failed", handler=handler.__name__, error=str(e))

    # ── ESCALACION ─────────────────────────────────────────────────────

    async def _escalate_critical(self, alert: Alert):
        """Escalacion automatica para alertas criticas."""
        logger.critical("alert_escalated", alert_id=alert.id, title=alert.title)
        
        # Notificar a todos los SUPER_ADMIN
        escalation_alert = Alert(
            alert_type="ESCALATION",
            severity="CRITICAL",
            title=f"ESCALACION: {alert.title}",
            message=f"Alerta critica requiere atencion inmediata: {alert.message}",
            source="ALERT_SYSTEM",
            investigation_id=alert.investigation_id,
            metadata={"original_alert_id": alert.id},
        )
        
        await self._distribute_alert(escalation_alert)

    # ── LIMPIEZA ─────────────────────────────────────────────────────────

    async def _cleanup_expired(self):
        """Limpia alertas expiradas periodicamente."""
        while True:
            try:
                await asyncio.sleep(300)  # Cada 5 minutos
                
                expired = [
                    alert_id for alert_id, alert in self.active_alerts.items()
                    if alert.is_expired()
                ]
                
                for alert_id in expired:
                    del self.active_alerts[alert_id]
                
                if expired:
                    logger.info("alerts_cleaned_up", count=len(expired))
                    
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error("cleanup_error", error=str(e))


# Instancia global
alert_manager = AlertManager()


# ── HANDLERS DE ALERTAS ESPECIFICAS ──────────────────────────────────

async def handle_darkweb_finding(alert: Alert):
    """Handler para hallazgos en dark web."""
    if alert.alert_type == "DARKWEB_HIGH_RISK_FINDING":
        # Crear alerta adicional para analistas
        await alert_manager.create_alert(
            alert_type="INTELIGENCE_BRIEF",
            severity="HIGH",
            title="Nuevo hallazgo en Dark Web",
            message=f"Se detecto contenido de alto riesgo: {alert.metadata.get('url', 'N/A')}",
            source="DARKWEB_MONITOR",
            investigation_id=alert.investigation_id,
            metadata=alert.metadata,
        )


async def handle_correlation_detection(alert: Alert):
    """Handler para correlaciones detectadas."""
    if alert.alert_type == "CORRELATION_DETECTED":
        severity = "HIGH" if alert.metadata.get("risk_score", 0) > 0.7 else "MEDIUM"
        await alert_manager.create_alert(
            alert_type="CORRELATION_ALERT",
            severity=severity,
            title="Correlacion significativa detectada",
            message=f"Nueva correlacion entre entidades con score {alert.metadata.get('risk_score', 0):.2f}",
            source="CORRELATION_ENGINE",
            investigation_id=alert.investigation_id,
            metadata=alert.metadata,
        )


async def handle_risk_escalation(alert: Alert):
    """Handler para escalacion de riesgo."""
    if alert.alert_type == "RISK_ESCALATION":
        await alert_manager.create_alert(
            alert_type="RISK_ALERT",
            severity=alert.severity,
            title=f"Riesgo escalado: {alert.metadata.get('person_uuid', 'Unknown')}",
            message=f"Score de riesgo incremento a {alert.metadata.get('new_score', 0):.2f}",
            source="RISK_SCORING",
            investigation_id=alert.investigation_id,
            metadata=alert.metadata,
        )

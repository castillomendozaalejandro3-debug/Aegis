"""Utilidades de seguridad - RBAC, autenticacion, autorizacion."""
from functools import wraps
from typing import Any, Callable, Dict, List, Optional

from fastapi import Depends, HTTPException, Request, Security, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt
from passlib.context import CryptContext

from src.config.settings import settings
from src.models.schemas import Role
from src.utils.logger import get_logger

logger = get_logger("aegis.security")

# ── PASSWORD HASHING ──────────────────────────────────────
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_password(password: str) -> str:
    """Genera hash bcrypt de contrasena."""
    return pwd_context.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verifica contrasena contra hash bcrypt."""
    return pwd_context.verify(plain_password, hashed_password)


# ── JWT ───────────────────────────────────────────────────
security = HTTPBearer()


def create_access_token(
    data: Dict[str, Any],
    expires_delta: Optional[int] = None,
) -> str:
    """Crea token JWT firmado.

    Args:
        data: Payload del token
        expires_delta: Horas hasta expiracion (default: settings.jwt_expiration_hours)

    Returns:
        Token JWT codificado
    """
    from datetime import datetime, timedelta

    to_encode = data.copy()
    expire = datetime.utcnow() + timedelta(
        hours=expires_delta or settings.jwt_expiration_hours
    )
    to_encode.update({"exp": expire, "iat": datetime.utcnow()})
    return jwt.encode(
        to_encode,
        settings.jwt_secret.get_secret_value(),
        algorithm=settings.jwt_algorithm,
    )


async def verify_token(
    credentials: HTTPAuthorizationCredentials = Security(security),
) -> Dict[str, Any]:
    """Verifica y decodifica token JWT.

    Args:
        credentials: Credenciales Bearer del header Authorization

    Returns:
        Payload decodificado del token

    Raises:
        HTTPException: 401 si el token es invalido o expiro
    """
    try:
        payload = jwt.decode(
            credentials.credentials,
            settings.jwt_secret.get_secret_value(),
            algorithms=[settings.jwt_algorithm],
        )
        # Validar campos requeridos
        if "sub" not in payload or "role" not in payload:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Token invalido: campos requeridos faltantes",
            )
        return payload
    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token invalido o expirado",
        )


def require_role(allowed_roles: List[Role]):
    """Decorador de dependencia para requerir roles especificos.

    Args:
        allowed_roles: Lista de roles permitidos

    Returns:
        Dependencia FastAPI que verifica el rol del usuario
    """
    allowed_values = [r.value for r in allowed_roles]

    async def role_checker(
        token: Dict[str, Any] = Depends(verify_token),
    ) -> Dict[str, Any]:
        user_role = token.get("role")
        if user_role not in allowed_values:
            logger.warning(
                "unauthorized_access_attempt",
                user=token.get("sub"),
                required_roles=allowed_values,
                actual_role=user_role,
            )
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Permisos insuficientes para esta operacion",
            )
        return token

    return role_checker


# ── RATE LIMITING AUXILIAR ──────────────────────────────
async def get_client_ip(request: Request) -> str:
    """Obtiene IP real del cliente considerando proxies."""
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


# ── SANITIZACION ─────────────────────────────────────────
import re


def sanitize_filename(filename: str) -> str:
    """Sanitiza nombre de archivo para prevenir path traversal.

    Args:
        filename: Nombre de archivo original

    Returns:
        Nombre de archivo seguro
    """
    from pathlib import Path

    name = Path(filename).name
    # Solo permitir caracteres seguros
    name = re.sub(r"[^a-zA-Z0-9._-]", "_", name)
    # Limitar longitud
    return name[:255]


def sanitize_cypher_query(query: str) -> str:
    """Valida que una query Cypher no contenga operaciones destructivas.

    Args:
        query: Query Cypher a validar

    Returns:
        Query validada

    Raises:
        ValueError: Si la query contiene operaciones no permitidas
    """
    forbidden_keywords = [
        "DELETE",
        "DETACH",
        "DROP",
        "REMOVE",
        "SET",
        "CREATE",
        "MERGE",
        "LOAD",
        "CALL",
        "apoc",
        "gds",
    ]

    query_upper = query.upper()
    for keyword in forbidden_keywords:
        # Buscar como palabra completa
        pattern = r"\b" + keyword + r"\b"
        if re.search(pattern, query_upper):
            raise ValueError(
                f"Query Cypher contiene operacion no permitida: {keyword}"
            )

    return query


# ── DEMO USERS (solo development) ─────────────────────────
DEMO_USERS = {
    "admin": {
        "password_hash": "$2b$12$LQv3c1yqBWVHxkd0LHAkCOYz6TtxMQJqhN8/X4.VTtYA.qGZvKG6G",  # 'changeme-2026!'
        "role": Role.SUPER_ADMIN.value,
        "is_active": True,
    },
}

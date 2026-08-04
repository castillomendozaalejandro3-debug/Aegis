"""Project Aegis-Peru - API REST con FastAPI, autenticacion JWT, rate limiting, RBAC."""
import os
import re
import tempfile
import uuid
from contextlib import asynccontextmanager
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional

import asyncpg
from fastapi import Depends, FastAPI, File, Form, HTTPException, Request, Security, UploadFile, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.responses import JSONResponse
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded

from src.config.settings import settings
from src.models.schemas import (
    AnalysisResult,
    APIResponse,
    HealthResponse,
    IngestPayload,
    InvestigationSchema,
    PaginatedResponse,
    Role,
)
from src.orchestrator import run_pipeline
from src.utils.crypto import generate_sha256
from src.utils.logger import get_logger, set_request_id
from src.utils.security import (
    create_access_token,
    hash_password,
    require_role,
    sanitize_cypher_query,
    sanitize_filename,
    verify_password,
    verify_token,
    DEMO_USERS,
)

logger = get_logger("aegis.api")

# ── RATE LIMITING ─────────────────────────────────────────
limiter = Limiter(key_func=get_remote_address)

# ── DB POOL ───────────────────────────────────────────────
db_pool: Optional[asyncpg.Pool] = None


async def get_db() -> asyncpg.Pool:
    if db_pool is None:
        raise HTTPException(status_code=503, detail="Base de datos no disponible")
    return db_pool


# ── LIFESPAN ──────────────────────────────────────────────
@asynccontextmanager
async def lifespan(app: FastAPI):
    global db_pool
    logger.info("api_startup")
    try:
        db_pool = await asyncpg.create_pool(
            settings.postgres_dsn.replace("+asyncpg", ""),
            min_size=5,
            max_size=settings.postgres_pool_size,
        )
        logger.info("database_pool_created")
    except Exception as e:
        logger.error("database_pool_failed", error=str(e))
        # No fallar el startup, permitir health check degradado
    yield
    if db_pool:
        await db_pool.close()
        logger.info("database_pool_closed")
    logger.info("api_shutdown")


# ── APP ───────────────────────────────────────────────────
app = FastAPI(
    title="Project Aegis-Peru",
    description="Sistema de Inteligencia OSINT para Investigacion Criminal",
    version="1.0.0",
    docs_url="/docs" if settings.environment != "production" else None,
    redoc_url="/redoc" if settings.environment != "production" else None,
    lifespan=lifespan,
)

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# CORS configurado segun entorno
allowed_origins = (
    ["https://aegis-peru.pnp.gob.pe"]
    if settings.environment == "production"
    else ["https://aegis-peru.pnp.gob.pe", "https://localhost:3000", "http://localhost:5173"]
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST"],
    allow_headers=["Authorization", "Content-Type", "X-Request-ID"],
)

app.add_middleware(
    TrustedHostMiddleware,
    allowed_hosts=["*.pnp.gob.pe", "localhost", "127.0.0.1", "aegis-peru.local"],
)


@app.middleware("http")
async def add_request_id(request: Request, call_next):
    rid = request.headers.get("X-Request-ID", str(uuid.uuid4()))
    set_request_id(rid)
    response = await call_next(request)
    response.headers["X-Request-ID"] = rid
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["X-XSS-Protection"] = "1; mode=block"
    return response


# ── HEALTH ────────────────────────────────────────────────
@app.get("/health", response_model=HealthResponse)
@limiter.limit("100/minute")
async def health_check(request: Request):
    services = {
        "api": "healthy",
        "database": "unknown",
        "neo4j": "unknown",
        "qdrant": "unknown",
        "redis": "unknown",
    }
    try:
        if db_pool:
            async with db_pool.acquire() as conn:
                await conn.fetchval("SELECT 1")
            services["database"] = "healthy"
    except Exception as e:
        services["database"] = f"unhealthy: {str(e)[:50]}"

    # Neo4j
    try:
        from src.nodes.persist_graph import _neo4j_client
        if _neo4j_client.verify_connectivity():
            services["neo4j"] = "healthy"
    except Exception as e:
        services["neo4j"] = f"unhealthy: {str(e)[:50]}"

    # Redis
    try:
        import redis.asyncio as aioredis
        r = aioredis.from_url(settings.redis_url)
        await r.ping()
        services["redis"] = "healthy"
        await r.close()
    except Exception as e:
        services["redis"] = f"unhealthy: {str(e)[:50]}"

    # Qdrant
    try:
        from qdrant_client import QdrantClient
        qc = QdrantClient(host=settings.qdrant_host, port=settings.qdrant_port)
        qc.get_collections()
        services["qdrant"] = "healthy"
    except Exception as e:
        services["qdrant"] = f"unhealthy: {str(e)[:50]}"

    overall = "healthy" if all(v == "healthy" for v in services.values()) else "degraded"
    return HealthResponse(status=overall, services=services)


@app.get("/health/ready")
@limiter.limit("100/minute")
async def readiness_check(request: Request):
    try:
        if db_pool:
            async with db_pool.acquire() as conn:
                await conn.fetchval("SELECT 1")
            return {"status": "ready"}
    except Exception:
        raise HTTPException(status_code=503, detail="Not ready")


# ── AUTH ENDPOINTS ────────────────────────────────────────
@app.post("/api/v1/auth/login")
@limiter.limit("5/minute")
async def login(request: Request, username: str = Form(...), password: str = Form(...)):
    """Autenticacion con verificacion contra base de datos o demo users (solo dev)."""
    request_id = set_request_id()

    # En produccion: verificar contra PostgreSQL
    if settings.environment == "production" and db_pool:
        async with db_pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT password_hash, role, is_active, mfa_enabled FROM users WHERE username = $1",
                username,
            )
            if not row or not row["is_active"]:
                logger.warning("failed_login_attempt", username=username, ip=request.client.host if request.client else "unknown")
                raise HTTPException(status_code=401, detail="Credenciales invalidas")

            if not verify_password(password, row["password_hash"]):
                logger.warning("failed_login_attempt", username=username, ip=request.client.host if request.client else "unknown")
                raise HTTPException(status_code=401, detail="Credenciales invalidas")

            token = create_access_token({
                "sub": username,
                "role": row["role"],
            })
            return {"access_token": token, "token_type": "bearer"}

    # Development: usar demo users (solo si no hay DB)
    elif settings.environment in ("development", "staging"):
        demo_user = DEMO_USERS.get(username)
        if demo_user and verify_password(password, demo_user["password_hash"]):
            if not demo_user["is_active"]:
                raise HTTPException(status_code=401, detail="Usuario desactivado")
            token = create_access_token({
                "sub": username,
                "role": demo_user["role"],
            })
            logger.info("demo_login_success", username=username, environment=settings.environment)
            return {"access_token": token, "token_type": "bearer"}

    logger.warning("failed_login_attempt", username=username, ip=request.client.host if request.client else "unknown")
    raise HTTPException(status_code=401, detail="Credenciales invalidas")


# ── INVESTIGATIONS ────────────────────────────────────────
@app.get("/api/v1/investigations", response_model=PaginatedResponse)
@limiter.limit("30/minute")
async def list_investigations(
    request: Request,
    page: int = 1,
    page_size: int = 20,
    status_filter: Optional[str] = None,
    token: Dict = Depends(require_role([Role.SUPER_ADMIN, Role.CASE_OFFICER, Role.ANALYST])),
):
    request_id = set_request_id()
    # TODO: Query a PostgreSQL con paginacion
    return PaginatedResponse(
        request_id=request_id,
        page=page,
        page_size=page_size,
        total=0,
        total_pages=0,
        data={"investigations": []},
    )


@app.post("/api/v1/investigations")
@limiter.limit("10/minute")
async def create_investigation(
    request: Request,
    investigation: InvestigationSchema,
    token: Dict = Depends(require_role([Role.SUPER_ADMIN, Role.CASE_OFFICER])),
):
    request_id = set_request_id()
    logger.info("create_investigation", case_id=investigation.case_id, title=investigation.title, user=token.get("sub"))
    # TODO: Persistir en PostgreSQL
    return APIResponse(
        request_id=request_id,
        data={"investigation": investigation.model_dump()},
    )


# ── INGEST (CORE) ─────────────────────────────────────────
@app.post("/api/v1/ingest")
@limiter.limit("30/minute")
async def ingest_evidence(
    request: Request,
    investigation_id: str = Form(..., pattern=r"^INV-\d{4}-\d{3}$"),
    image: Optional[UploadFile] = File(None),
    text_query: Optional[str] = Form(None),
    dni_hint: Optional[str] = Form(None, pattern=r"^\d{8}$"),
    ruc_hint: Optional[str] = Form(None, pattern=r"^\d{11}$"),
    alias_hint: Optional[str] = Form(None),
    phone_hint: Optional[str] = Form(None),
    email_hint: Optional[str] = Form(None),
    source_tags: Optional[str] = Form(""),
    token: Dict = Depends(require_role([Role.SUPER_ADMIN, Role.CASE_OFFICER, Role.ANALYST])),
):
    request_id = set_request_id()
    logger.info(
        "ingest_request",
        investigation_id=investigation_id,
        user=token.get("sub"),
        has_image=image is not None,
        text_query=text_query,
    )

    # Validar y procesar imagen con streaming
    image_bytes = None
    image_filename = None
    if image:
        if image.content_type not in settings.allowed_image_types:
            raise HTTPException(status_code=400, detail="Tipo de imagen no permitido")

        # Stream a archivo temporal en lugar de memoria
        with tempfile.NamedTemporaryFile(delete=False, dir=settings.upload_storage_path) as tmp:
            total_size = 0
            chunk_size = 8192
            while chunk := await image.read(chunk_size):
                total_size += len(chunk)
                if total_size > settings.max_file_size_mb * 1024 * 1024:
                    os.unlink(tmp.name)
                    raise HTTPException(status_code=413, detail=f"Imagen excede {settings.max_file_size_mb}MB")
                tmp.write(chunk)

            tmp_path = Path(tmp.name)
            image_bytes = tmp_path.read_bytes()
            tmp_path.unlink()
            image_filename = sanitize_filename(image.filename) if image.filename else "unknown"

    # Construir payload
    payload = IngestPayload(
        investigation_id=investigation_id,
        image_bytes=image_bytes,
        image_filename=image_filename,
        text_query=text_query,
        dni_hint=dni_hint,
        ruc_hint=ruc_hint,
        alias_hint=alias_hint,
        phone_hint=phone_hint,
        email_hint=email_hint,
        source_tags=source_tags.split(",") if source_tags else [],
    )

    # Ejecutar pipeline
    final_state = run_pipeline(payload, investigation_id)

    if final_state.get("pipeline_status") == "COMPLETED":
        return APIResponse(
            request_id=request_id,
            message="Analisis completado exitosamente",
            data={
                "investigation_id": investigation_id,
                "status": "COMPLETED",
                "processing_time": final_state.get("processing_time_seconds"),
                "analysis": final_state.get("analysis_result", {}),
            },
        )
    else:
        raise HTTPException(
            status_code=500,
            detail=f"Error en pipeline: {final_state.get('error', 'Unknown error')}",
        )


# ── QUERY ─────────────────────────────────────────────────
@app.post("/api/v1/query")
@limiter.limit("60/minute")
async def query_graph(
    request: Request,
    cypher_query: str = Form(...),
    token: Dict = Depends(require_role([Role.SUPER_ADMIN, Role.ANALYST])),
):
    request_id = set_request_id()
    logger.info("query_graph", request_id=request_id, user=token.get("sub"))

    # Validar query Cypher
    try:
        sanitized_query = sanitize_cypher_query(cypher_query)
    except ValueError as e:
        logger.warning("forbidden_cypher_query", user=token.get("sub"), query=cypher_query[:100])
        raise HTTPException(status_code=400, detail=str(e))

    # Ejecutar contra Neo4j
    try:
        from src.nodes.persist_graph import _neo4j_client
        with _neo4j_client._get_driver().session() as session:
            result = session.run(sanitized_query + " LIMIT 1000", timeout=30)
            records = [record.data() for record in result]
            return APIResponse(
                request_id=request_id,
                data={"results": records, "count": len(records), "query": cypher_query},
            )
    except Exception as e:
        logger.error("cypher_execution_error", error=str(e))
        raise HTTPException(status_code=400, detail="Error en ejecucion de query")


# ── EXPORT ────────────────────────────────────────────────
@app.get("/api/v1/export/{investigation_id}")
@limiter.limit("10/minute")
async def export_investigation(
    request: Request,
    investigation_id: str,
    format: str = "json",
    token: Dict = Depends(require_role([Role.SUPER_ADMIN, Role.CASE_OFFICER, Role.ANALYST])),
):
    request_id = set_request_id()
    logger.info("export_request", investigation_id=investigation_id, format=format, user=token.get("sub"))
    # TODO: Implementar export real
    return APIResponse(
        request_id=request_id,
        data={"investigation_id": investigation_id, "format": format, "download_url": None},
    )


# ── ERROR HANDLERS ────────────────────────────────────────
@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "success": False,
            "message": exc.detail,
            "request_id": set_request_id(),
            "timestamp": datetime.utcnow().isoformat(),
        },
    )


@app.exception_handler(Exception)
async def general_exception_handler(request: Request, exc: Exception):
    logger.error("unhandled_exception", error=str(exc), path=request.url.path)
    return JSONResponse(
        status_code=500,
        content={
            "success": False,
            "message": "Error interno del servidor",
            "request_id": set_request_id(),
            "timestamp": datetime.utcnow().isoformat(),
        },
    )

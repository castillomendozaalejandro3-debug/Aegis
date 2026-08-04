"""Configuracion centralizada - Pydantic Settings v2 con Vault integration."""
import os
from functools import lru_cache
from typing import Optional, Set

from pydantic import Field, SecretStr, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


# Lista de secretos por defecto prohibidos en produccion
DEFAULT_SECRETS_BLACKLIST: Set[str] = {
    "aegis-peru-2026",
    "aegis-secure-2026",
    "aegis-redis-2026",
    "aegis-jwt-secret-2026",
    "aegis-vault-dev",
    "aegis-grafana-2026",
    "aegis",
    "admin",
    "password",
    "123456",
    "secret",
}


class AegisSettings(BaseSettings):
    """Configuracion de Project Aegis-Peru con validacion estricta."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # ── ENTORNO ─────────────────────────────────────────────
    environment: str = Field(default="development", alias="AEGIS_ENV")

    # ── NEO4J ──────────────────────────────────────────────
    neo4j_uri: str = Field(default="bolt://neo4j:7687", alias="NEO4J_URI")
    neo4j_user: str = Field(default="neo4j", alias="NEO4J_USER")
    neo4j_password: SecretStr = Field(alias="NEO4J_PASSWORD")
    neo4j_max_pool_size: int = Field(default=50, alias="NEO4J_MAX_POOL_SIZE")

    # ── QDRANT ───────────────────────────────────────────
    qdrant_host: str = Field(default="qdrant", alias="QDRANT_HOST")
    qdrant_port: int = Field(default=6333, alias="QDRANT_PORT")
    qdrant_api_key: SecretStr = Field(default=SecretStr(""), alias="QDRANT_API_KEY")
    qdrant_collection: str = Field(default="aegis_entities", alias="QDRANT_COLLECTION")

    # ── POSTGRESQL ─────────────────────────────────────────
    postgres_dsn: str = Field(
        default="postgresql+asyncpg://aegis:aegis@postgres:5432/aegis_peru",
        alias="POSTGRES_DSN",
    )
    postgres_pool_size: int = Field(default=20, alias="POSTGRES_POOL_SIZE")

    # ── REDIS / CELERY ────────────────────────────────────
    redis_url: str = Field(
        default="redis://:aegis-redis-2026@redis:6379/0", alias="REDIS_URL"
    )
    celery_broker_url: Optional[str] = Field(default=None, alias="CELERY_BROKER_URL")
    celery_result_backend: Optional[str] = Field(default=None, alias="CELERY_RESULT_BACKEND")

    # ── TOR / ANONIMATO ───────────────────────────────────
    tor_proxy: str = Field(default="socks5h://tor-gateway:9050", alias="TOR_PROXY")
    tor_control_port: int = Field(default=9051, alias="TOR_CONTROL_PORT")
    tor_control_password: SecretStr = Field(
        default=SecretStr(""), alias="TOR_CONTROL_PASSWORD"
    )
    tor_verify_ip: bool = Field(default=True, alias="TOR_VERIFY_IP")
    tor_max_retries: int = Field(default=3, alias="TOR_MAX_RETRIES")

    # ── VAULT ─────────────────────────────────────────────
    vault_addr: str = Field(default="http://vault-agent:8200", alias="VAULT_ADDR")
    vault_token: SecretStr = Field(default=SecretStr(""), alias="VAULT_TOKEN")
    vault_mount_point: str = Field(default="secret", alias="VAULT_MOUNT_POINT")
    vault_path: str = Field(default="aegis-peru", alias="VAULT_PATH")

    # ── API KEYS EXTERNAS ─────────────────────────────────
    shodan_api_key: SecretStr = Field(default=SecretStr(""), alias="SHODAN_API_KEY")
    censys_api_id: SecretStr = Field(default=SecretStr(""), alias="CENSYS_API_ID")
    censys_api_secret: SecretStr = Field(default=SecretStr(""), alias="CENSYS_API_SECRET")
    openai_api_key: SecretStr = Field(default=SecretStr(""), alias="OPENAI_API_KEY")
    openai_model: str = Field(default="gpt-4o", alias="OPENAI_MODEL")

    # ── mTLS ──────────────────────────────────────────────
    mtls_enabled: bool = Field(default=True, alias="MTLS_ENABLED")
    mtls_cert_path: str = Field(default="/certs/client.crt", alias="MTLS_CERT_PATH")
    mtls_key_path: str = Field(default="/certs/client.key", alias="MTLS_KEY_PATH")
    mtls_ca_path: str = Field(default="/certs/ca.crt", alias="MTLS_CA_PATH")

    # ── LOGGING ───────────────────────────────────────────
    log_level: str = Field(default="INFO", alias="LOG_LEVEL")
    json_logs: bool = Field(default=True, alias="JSON_LOGS")
    log_request_id: bool = Field(default=True, alias="LOG_REQUEST_ID")

    # ── SEGURIDAD ─────────────────────────────────────────
    jwt_secret: SecretStr = Field(alias="JWT_SECRET")
    jwt_algorithm: str = Field(default="HS256", alias="JWT_ALGORITHM")
    jwt_expiration_hours: int = Field(default=8, alias="JWT_EXPIRATION_HOURS")
    mfa_enabled: bool = Field(default=True, alias="MFA_ENABLED")

    # ── RATE LIMITING ──────────────────────────────────────
    rate_limit_requests: int = Field(default=100, alias="RATE_LIMIT_REQUESTS")
    rate_limit_window: int = Field(default=60, alias="RATE_LIMIT_WINDOW")

    # ── AEGIS CORE ─────────────────────────────────────────
    max_file_size_mb: int = Field(default=50, alias="MAX_FILE_SIZE_MB")
    allowed_image_types: list[str] = Field(
        default=["image/jpeg", "image/png", "image/webp", "image/tiff"],
        alias="ALLOWED_IMAGE_TYPES",
    )
    evidence_storage_path: str = Field(default="/app/evidence", alias="EVIDENCE_STORAGE_PATH")
    upload_storage_path: str = Field(default="/app/uploads", alias="UPLOAD_STORAGE_PATH")

    # ── LANGGRAPH ──────────────────────────────────────────
    graph_checkpoint_interval: int = Field(default=5, alias="GRAPH_CHECKPOINT_INTERVAL")
    graph_max_iterations: int = Field(default=20, alias="GRAPH_MAX_ITERATIONS")
    graph_timeout_seconds: int = Field(default=300, alias="GRAPH_TIMEOUT_SECONDS")

    # ── SCRAPERS ─────────────────────────────────────────
    scraper_timeout: int = Field(default=30, alias="SCRAPER_TIMEOUT")
    scraper_max_retries: int = Field(default=3, alias="SCRAPER_MAX_RETRIES")
    scraper_delay_min: float = Field(default=2.0, alias="SCRAPER_DELAY_MIN")
    scraper_delay_max: float = Field(default=5.0, alias="SCRAPER_DELAY_MAX")
    scraper_headless: bool = Field(default=True, alias="SCRAPER_HEADLESS")

    @field_validator("log_level")
    @classmethod
    def validate_log_level(cls, v: str) -> str:
        allowed = {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}
        v_upper = v.upper()
        if v_upper not in allowed:
            raise ValueError(f"log_level must be one of {allowed}")
        return v_upper

    @field_validator("environment")
    @classmethod
    def validate_environment(cls, v: str) -> str:
        allowed = {"development", "staging", "production"}
        v_lower = v.lower()
        if v_lower not in allowed:
            raise ValueError(f"environment must be one of {allowed}")
        return v_lower

    @field_validator("celery_broker_url", "celery_result_backend")
    @classmethod
    def default_celery_from_redis(cls, v: Optional[str], info) -> str:
        if v is None or v == "":
            return info.data.get("redis_url", "redis://localhost:6379/0")
        return v

    @model_validator(mode="after")
    def validate_production_secrets(self):
        """Valida que no se usen secretos por defecto en produccion."""
        if self.environment == "production":
            secrets_to_check = [
                ("jwt_secret", self.jwt_secret.get_secret_value()),
                ("neo4j_password", self.neo4j_password.get_secret_value()),
            ]
            for name, value in secrets_to_check:
                if value in DEFAULT_SECRETS_BLACKLIST or len(value) < 32:
                    raise ValueError(
                        f"{name} usa un secreto debil o por defecto en produccion. "
                        f"Debe tener al menos 32 caracteres y no estar en la lista negra."
                    )
        return self

    @property
    def neo4j_auth(self) -> tuple[str, str]:
        return (self.neo4j_user, self.neo4j_password.get_secret_value())

    @property
    def qdrant_url(self) -> str:
        return f"http://{self.qdrant_host}:{self.qdrant_port}"


@lru_cache()
def get_settings() -> AegisSettings:
    """Singleton de configuracion con cache."""
    return AegisSettings()


settings = get_settings()

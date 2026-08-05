"""Esquemas Pydantic v2 - Modelos de datos con validacion estricta."""
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field, field_validator


# ── ENUMS ──────────────────────────────────────────────────

class InvestigationStatus(str, Enum):
    ACTIVE = "ACTIVE"
    CLOSED = "CLOSED"
    PENDING = "PENDING"
    ARCHIVED = "ARCHIVED"


class Priority(str, Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class ContactType(str, Enum):
    PHONE = "PHONE"
    EMAIL = "EMAIL"
    SOCIAL = "SOCIAL"
    MESSAGING = "MESSAGING"


class AssetType(str, Enum):
    IMAGE = "IMAGE"
    VIDEO = "VIDEO"
    DOCUMENT = "DOCUMENT"
    AUDIO = "AUDIO"


class Role(str, Enum):
    SUPER_ADMIN = "SUPER_ADMIN"
    CASE_OFFICER = "CASE_OFFICER"
    ANALYST = "ANALYST"
    AUDITOR = "AUDITOR"
    SYSTEM = "SYSTEM"


class Gender(str, Enum):
    MALE = "M"
    FEMALE = "F"


class PersonType(str, Enum):
    NATURAL = "NATURAL"
    JURIDICA = "JURIDICA"


class TaxCondition(str, Enum):
    HABIDO = "HABIDO"
    NO_HABIDO = "NO_HABIDO"


class RegistryStatus(str, Enum):
    ACTIVO = "ACTIVO"
    INACTIVO = "INACTIVO"
    SUSPENDIDO = "SUSPENDIDO"


# ── MODELOS BASE ──────────────────────────────────────────

class PersonSchema(BaseModel):
    """Esquema de persona - victima, sospechoso, testigo."""
    uuid: str = Field(..., description="UUID v4 unico de la entidad")
    dni: Optional[str] = Field(
        None, pattern=r"^\d{8}$", description="DNI peruano de 8 digitos"
    )
    full_name: Optional[str] = Field(None, max_length=200)
    alias: List[str] = Field(default_factory=list)
    date_of_birth: Optional[str] = None
    nationality: str = Field(default="Peruana", max_length=50)
    gender: Optional[Gender] = None
    risk_score: float = Field(default=0.0, ge=0.0, le=1.0)
    status: str = Field(default="ACTIVE")
    source: str = Field(..., min_length=1)
    confidence: float = Field(..., ge=0.0, le=1.0)
    investigation_id: str = Field(..., pattern=r"^INV-\d{4}-\d{3}$")

    @field_validator("date_of_birth")
    @classmethod
    def validate_dob_format(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return v
        try:
            datetime.strptime(v, "%Y-%m-%d")
        except ValueError:
            raise ValueError("date_of_birth must be YYYY-MM-DD format")
        return v


class ContactSchema(BaseModel):
    """Esquema de contacto - telefono, email, redes sociales."""
    uuid: str
    contact_type: ContactType
    value: str = Field(..., min_length=3, max_length=500)
    carrier: Optional[str] = None
    domain: Optional[str] = None
    is_verified: bool = False
    source: str
    confidence: float = Field(..., ge=0.0, le=1.0)
    investigation_id: str = Field(..., pattern=r"^INV-\d{4}-\d{3}$")


class LocationSchema(BaseModel):
    """Esquema de ubicacion geoespacial."""
    uuid: str
    latitude: float = Field(..., ge=-90.0, le=90.0)
    longitude: float = Field(..., ge=-180.0, le=180.0)
    address: Optional[str] = None
    city: Optional[str] = None
    region: Optional[str] = None
    country: str = Field(default="PE", pattern=r"^[A-Z]{2}$")
    timestamp: Optional[datetime] = None
    accuracy_meters: Optional[int] = Field(None, ge=0)
    source: str
    confidence: float = Field(..., ge=0.0, le=1.0)
    investigation_id: str = Field(..., pattern=r"^INV-\d{4}-\d{3}$")


class AssetSchema(BaseModel):
    """Esquema de activo digital - imagen, video, documento."""
    uuid: str
    asset_type: AssetType
    hash: str = Field(..., min_length=64, max_length=128)
    filename: str = Field(..., max_length=500)
    mime_type: str
    size_bytes: int = Field(..., ge=0)
    exif_data: Optional[Dict[str, Any]] = None
    storage_path: str
    source: str
    confidence: float = Field(..., ge=0.0, le=1.0)
    investigation_id: str = Field(..., pattern=r"^INV-\d{4}-\d{3}$")

    @field_validator("mime_type")
    @classmethod
    def validate_mime(cls, v: str) -> str:
        allowed = {"image/jpeg", "image/png", "image/webp", "image/tiff",
                   "video/mp4", "video/avi", "application/pdf", "audio/mpeg"}
        if v not in allowed:
            raise ValueError(f"mime_type must be one of {allowed}")
        return v


class DigitalFootprintSchema(BaseModel):
    """Huella digital en plataformas publicas."""
    uuid: str
    platform: str
    url: Optional[str] = None
    username: Optional[str] = None
    content_snippet: Optional[str] = None
    scraped_at: Optional[datetime] = None
    source: str
    confidence: float = Field(..., ge=0.0, le=1.0)
    investigation_id: str = Field(..., pattern=r"^INV-\d{4}-\d{3}$")


class DarkWebProfileSchema(BaseModel):
    """Perfil en dark web / foros .onion."""
    uuid: str
    onion_url: str = Field(..., pattern=r"^http://[a-z2-7]{56}\.onion.*$")
    username: Optional[str] = None
    platform_name: Optional[str] = None
    reputation_score: Optional[float] = Field(None, ge=0.0, le=5.0)
    activity_summary: Optional[str] = None
    first_seen: Optional[datetime] = None
    last_seen: Optional[datetime] = None
    source: str
    confidence: float = Field(..., ge=0.0, le=1.0)
    investigation_id: str = Field(..., pattern=r"^INV-\d{4}-\d{3}$")


class InvestigationSchema(BaseModel):
    """Caso de investigacion."""
    case_id: str = Field(..., pattern=r"^INV-\d{4}-\d{3}$")
    title: str = Field(..., max_length=300)
    description: Optional[str] = None
    status: InvestigationStatus = InvestigationStatus.ACTIVE
    priority: Priority = Priority.MEDIUM
    assigned_unit: Optional[str] = None
    lead_officer: Optional[str] = None
    classification: Optional[str] = Field(default="SECRET")
    tags: List[str] = Field(default_factory=list)
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class RelationshipSchema(BaseModel):
    """Relacion entre entidades en el grafo."""
    source_uuid: str
    target_uuid: str
    relationship_type: str
    properties: Dict[str, Any] = Field(default_factory=dict)
    confidence: float = Field(..., ge=0.0, le=1.0)
    source: str


# ── REGISTRO PERUANO ─────────────────────────────────────

class SunatResult(BaseModel):
    """Resultado de consulta SUNAT."""
    ruc: str = Field(..., pattern=r"^\d{11}$")
    razon_social: str
    tipo_persona: PersonType
    estado: RegistryStatus
    condicion_domicilio: TaxCondition
    direccion: Optional[str] = None
    departamento: Optional[str] = None
    provincia: Optional[str] = None
    distrito: Optional[str] = None
    actividad_economica: Optional[List[str]] = Field(default_factory=list)
    fecha_inscripcion: Optional[str] = None
    fecha_inicio_actividades: Optional[str] = None
    sistema_emision: Optional[str] = None
    sistema_contabilidad: Optional[str] = None
    telefono: Optional[str] = None
    fax: Optional[str] = None
    comprobante_pago: Optional[List[str]] = Field(default_factory=list)
    source: str = Field(default="SUNAT")
    confidence: float = Field(default=0.95, ge=0.0, le=1.0)
    queried_at: datetime = Field(default_factory=datetime.utcnow)


class DniResult(BaseModel):
    """Resultado de consulta DNI/RENIEC."""
    dni: str = Field(..., pattern=r"^\d{8}$")
    nombres: Optional[str] = None
    apellido_paterno: Optional[str] = None
    apellido_materno: Optional[str] = None
    full_name: Optional[str] = None
    fecha_nacimiento: Optional[str] = None
    sexo: Optional[Gender] = None
    estado_civil: Optional[str] = None
    ubigeo_nacimiento: Optional[str] = None
    direccion: Optional[str] = None
    ubigeo_direccion: Optional[str] = None
    foto_url: Optional[str] = None
    source: str = Field(default="RENIEC")
    confidence: float = Field(default=0.90, ge=0.0, le=1.0)
    queried_at: datetime = Field(default_factory=datetime.utcnow)


class SuneduResult(BaseModel):
    """Resultado de consulta SUNEDU."""
    dni: Optional[str] = Field(None, pattern=r"^\d{8}$")
    nombres: Optional[str] = None
    apellidos: Optional[str] = None
    universidad: Optional[str] = None
    carrera: Optional[str] = None
    grado: Optional[str] = None
    fecha_grado: Optional[str] = None
    resolucion: Optional[str] = None
    tipo_documento: Optional[str] = None
    source: str = Field(default="SUNEDU")
    confidence: float = Field(default=0.85, ge=0.0, le=1.0)
    queried_at: datetime = Field(default_factory=datetime.utcnow)


class SunarpResult(BaseModel):
    """Resultado de consulta SUNARP."""
    titular: Optional[str] = None
    tipo_bien: Optional[str] = None
    direccion: Optional[str] = None
    placa: Optional[str] = None
    ruc: Optional[str] = None
    partida_registral: Optional[str] = None
    area: Optional[str] = None
    valor: Optional[str] = None
    fecha_inscripcion: Optional[str] = None
    source: str = Field(default="SUNARP")
    confidence: float = Field(default=0.80, ge=0.0, le=1.0)
    queried_at: datetime = Field(default_factory=datetime.utcnow)


class BreachResult(BaseModel):
    """Resultado de consulta de breach data."""
    email: Optional[str] = None
    phone: Optional[str] = None
    breaches: List[Dict[str, Any]] = Field(default_factory=list)
    data_classes: List[str] = Field(default_factory=list)
    is_compromised: bool = False
    compromise_count: int = 0
    source: str = Field(default="BREACH_DB")
    confidence: float = Field(default=0.75, ge=0.0, le=1.0)
    queried_at: datetime = Field(default_factory=datetime.utcnow)


# ── PAYLOADS DE INGESTA ──────────────────────────────────

class IngestPayload(BaseModel):
    """Payload de ingesta de evidencia."""
    investigation_id: str = Field(..., pattern=r"^INV-\d{4}-\d{3}$")
    image_bytes: Optional[bytes] = None
    image_filename: Optional[str] = None
    text_query: Optional[str] = None
    dni_hint: Optional[str] = Field(None, pattern=r"^\d{8}$")
    ruc_hint: Optional[str] = Field(None, pattern=r"^\d{11}$")
    alias_hint: Optional[str] = None
    phone_hint: Optional[str] = None
    email_hint: Optional[str] = None
    source_tags: List[str] = Field(default_factory=list)

    @field_validator("image_bytes")
    @classmethod
    def validate_image_size(cls, v: Optional[bytes]) -> Optional[bytes]:
        if v is not None and len(v) > 50 * 1024 * 1024:  # 50MB
            raise ValueError("image_bytes exceeds 50MB limit")
        return v


# ── RESULTADOS DE ANALISIS ───────────────────────────────

class AnalysisResult(BaseModel):
    """Resultado completo del pipeline de analisis."""
    investigation_id: str
    extracted_entities: Dict[str, List[Dict[str, Any]]] = Field(default_factory=dict)
    locations: List[LocationSchema] = Field(default_factory=list)
    contacts: List[ContactSchema] = Field(default_factory=list)
    assets: List[AssetSchema] = Field(default_factory=list)
    darkweb_profiles: List[DarkWebProfileSchema] = Field(default_factory=list)
    persons: List[PersonSchema] = Field(default_factory=list)
    digital_footprints: List[DigitalFootprintSchema] = Field(default_factory=list)
    sunat_results: List[SunatResult] = Field(default_factory=list)
    dni_results: List[DniResult] = Field(default_factory=list)
    sunedu_results: List[SuneduResult] = Field(default_factory=list)
    sunarp_results: List[SunarpResult] = Field(default_factory=list)
    breach_results: List[BreachResult] = Field(default_factory=list)
    confidence_aggregate: float = Field(default=0.0, ge=0.0, le=1.0)
    processing_metadata: Dict[str, Any] = Field(default_factory=dict)
    processing_time_seconds: float = Field(default=0.0, ge=0.0)
    threat_indicators: List[str] = Field(default_factory=list)


# ── RESPUESTAS API ───────────────────────────────────────

class APIResponse(BaseModel):
    """Respuesta estandar de API."""
    success: bool = True
    message: str = "Operacion exitosa"
    data: Optional[Dict[str, Any]] = None
    request_id: str
    timestamp: datetime = Field(default_factory=datetime.utcnow)


class PaginatedResponse(APIResponse):
    """Respuesta paginada."""
    page: int = 1
    page_size: int = 20
    total: int = 0
    total_pages: int = 0


class HealthResponse(BaseModel):
    """Respuesta de health check."""
    status: str = "healthy"
    version: str = "1.0.0"
    services: Dict[str, str] = Field(default_factory=dict)
    timestamp: datetime = Field(default_factory=datetime.utcnow)

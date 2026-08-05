"""Nodo de persistencia - Inyeccion en grafo de conocimiento Neo4j con circuit breaker."""
import json
from datetime import datetime
from typing import Any, Dict, List, Optional

from neo4j import GraphDatabase
from tenacity import retry, stop_after_attempt, wait_exponential

from src.config.settings import settings
from src.models.schemas import AnalysisResult
from src.utils.logger import get_logger

logger = get_logger("aegis.node.persist")


class Neo4jPersistence:
    """Cliente Neo4j con connection pooling, retry y circuit breaker."""

    def __init__(self):
        self._driver = None
        self._circuit_open = False
        self._failure_count = 0
        self._failure_threshold = 5
        self._last_failure_time = None

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        reraise=True,
    )
    def _get_driver(self):
        """Obtiene driver Neo4j con retry y circuit breaker."""
        if self._circuit_open:
            # Verificar si debemos cerrar el circuito (30 segundos)
            if self._last_failure_time:
                elapsed = (datetime.utcnow() - self._last_failure_time).total_seconds()
                if elapsed > 30:
                    self._circuit_open = False
                    self._failure_count = 0
                    logger.info("neo4j_circuit_breaker_reset")
                else:
                    raise ConnectionError("Circuit breaker abierto - Neo4j no disponible")

        try:
            if self._driver is None:
                self._driver = GraphDatabase.driver(
                    settings.neo4j_uri,
                    auth=settings.neo4j_auth,
                    max_connection_pool_size=settings.neo4j_max_pool_size,
                    connection_timeout=10,
                    keep_alive=True,
                )
            # Verificar conectividad
            self._driver.verify_connectivity()
            self._failure_count = 0
            return self._driver
        except Exception as e:
            self._failure_count += 1
            self._last_failure_time = datetime.utcnow()
            if self._failure_count >= self._failure_threshold:
                self._circuit_open = True
                logger.critical("neo4j_circuit_breaker_opened", failures=self._failure_count)
            raise

    def close(self):
        """Cierra conexion Neo4j."""
        if self._driver:
            try:
                self._driver.close()
            except Exception as e:
                logger.warning("neo4j_close_error", error=str(e))
            finally:
                self._driver = None

    def verify_connectivity(self) -> bool:
        """Verifica conectividad con Neo4j."""
        try:
            with self._get_driver().session() as session:
                session.run("RETURN 1")
            return True
        except Exception as e:
            logger.error("neo4j_connectivity_failed", error=str(e))
            return False


_neo4j_client = Neo4jPersistence()


def persist_graph_node(state: Dict[str, Any]) -> Dict[str, Any]:
    """Nodo LangGraph: Persiste entidades en Neo4j.

    Args:
        state: Estado actual con analysis_result

    Returns:
        Estado actualizado
    """
    logger.info("persist_graph_start")

    analysis_data = state.get("analysis_result", {})
    if not analysis_data:
        state["error"] = "No hay datos de analisis para persistir"
        state["stage"] = "persist_failed"
        logger.error("persist_graph_failed", reason="no_analysis_data")
        return state

    try:
        result = AnalysisResult(**analysis_data)
    except Exception as e:
        state["error"] = f"Error validando AnalysisResult: {str(e)}"
        state["stage"] = "persist_failed"
        logger.error("persist_graph_validation_error", error=str(e))
        return state

    if not _neo4j_client.verify_connectivity():
        state["error"] = "Neo4j no disponible"
        state["stage"] = "persist_failed"
        logger.error("persist_graph_failed", reason="neo4j_unavailable")
        return state

    try:
        with _neo4j_client._get_driver().session() as session:
            # Crear investigacion
            _persist_investigation(session, result)

            # Persistir entidades
            for person in result.persons:
                _persist_person(session, person, result.investigation_id)
            for contact in result.contacts:
                _persist_contact(session, contact, result.investigation_id)
            for location in result.locations:
                _persist_location(session, location, result.investigation_id)
            for asset in result.assets:
                _persist_asset(session, asset, result.investigation_id)
            for dw in result.darkweb_profiles:
                _persist_darkweb(session, dw, result.investigation_id)
            for df in result.digital_footprints:
                _persist_digital_footprint(session, df, result.investigation_id)
            for sr in result.sunat_results:
                _persist_sunat(session, sr, result.investigation_id)
            for dr in result.dni_results:
                _persist_dni(session, dr, result.investigation_id)
            for br in result.breach_results:
                _persist_breach(session, br, result.investigation_id)

            # Crear relaciones
            _create_relationships(session, result)

        state["stage"] = "persist_complete"
        state["persisted"] = True
        logger.info(
            "persist_graph_complete",
            investigation_id=result.investigation_id,
            persons=len(result.persons),
            contacts=len(result.contacts),
            locations=len(result.locations),
            assets=len(result.assets),
            sunat=len(result.sunat_results),
            dni=len(result.dni_results),
            breaches=len(result.breach_results),
        )

    except Exception as e:
        state["error"] = f"Error persistiendo en Neo4j: {str(e)}"
        state["stage"] = "persist_failed"
        logger.error("persist_graph_error", error=str(e))

    return state


def _persist_investigation(session, result: AnalysisResult) -> None:
    query = """
    MERGE (i:Investigation {case_id: $case_id})
    ON CREATE SET
        i.title = $title,
        i.status = $status,
        i.priority = $priority,
        i.created_at = datetime(),
        i.updated_at = datetime(),
        i.confidence = $confidence
    ON MATCH SET
        i.updated_at = datetime(),
        i.confidence = $confidence
    """
    session.run(query, {
        "case_id": result.investigation_id,
        "title": f"Investigacion {result.investigation_id}",
        "status": "ACTIVE",
        "priority": "CRITICAL",
        "confidence": result.confidence_aggregate,
    })


def _persist_person(session, person: Any, investigation_id: str) -> None:
    if isinstance(person, dict):
        person_dict = person
    else:
        person_dict = person.model_dump()

    query = """
    MERGE (p:Person {uuid: $uuid})
    ON CREATE SET
        p.dni = $dni,
        p.full_name = $full_name,
        p.alias = $alias,
        p.date_of_birth = $dob,
        p.nationality = $nationality,
        p.gender = $gender,
        p.risk_score = $risk_score,
        p.status = $status,
        p.source = $source,
        p.confidence = $confidence,
        p.created_at = datetime(),
        p.updated_at = datetime()
    ON MATCH SET
        p.updated_at = datetime(),
        p.confidence = CASE WHEN $confidence > p.confidence THEN $confidence ELSE p.confidence END
    WITH p
    MATCH (i:Investigation {case_id: $inv_id})
    MERGE (i)-[:INVESTIGATES {role: 'SUBJECT', added_at: datetime()}]->(p)
    """
    session.run(query, {
        "uuid": person_dict.get("uuid"),
        "dni": person_dict.get("dni"),
        "full_name": person_dict.get("full_name"),
        "alias": person_dict.get("alias", []),
        "dob": person_dict.get("date_of_birth"),
        "nationality": person_dict.get("nationality", "Peruana"),
        "gender": person_dict.get("gender"),
        "risk_score": person_dict.get("risk_score", 0.0),
        "status": person_dict.get("status", "ACTIVE"),
        "source": person_dict.get("source"),
        "confidence": person_dict.get("confidence", 0.0),
        "inv_id": investigation_id,
    })


def _persist_contact(session, contact: Any, investigation_id: str) -> None:
    if isinstance(contact, dict):
        contact_dict = contact
    else:
        contact_dict = contact.model_dump()

    query = """
    MERGE (c:Contact {uuid: $uuid})
    ON CREATE SET
        c.contact_type = $contact_type,
        c.value = $value,
        c.carrier = $carrier,
        c.domain = $domain,
        c.is_verified = $is_verified,
        c.source = $source,
        c.confidence = $confidence,
        c.created_at = datetime()
    WITH c
    MATCH (i:Investigation {case_id: $inv_id})
    MERGE (i)-[:HAS_CONTACT]->(c)
    """
    session.run(query, {
        "uuid": contact_dict.get("uuid"),
        "contact_type": contact_dict.get("contact_type", "PHONE"),
        "value": contact_dict.get("value"),
        "carrier": contact_dict.get("carrier"),
        "domain": contact_dict.get("domain"),
        "is_verified": contact_dict.get("is_verified", False),
        "source": contact_dict.get("source"),
        "confidence": contact_dict.get("confidence", 0.0),
        "inv_id": investigation_id,
    })


def _persist_location(session, location: Any, investigation_id: str) -> None:
    if isinstance(location, dict):
        loc_dict = location
    else:
        loc_dict = location.model_dump()

    lat = loc_dict.get("latitude")
    lon = loc_dict.get("longitude")

    query = """
    MERGE (l:Location {uuid: $uuid})
    ON CREATE SET
        l.coordinates = point({latitude: $lat, longitude: $lon}),
        l.address = $address,
        l.city = $city,
        l.region = $region,
        l.country = $country,
        l.timestamp = $timestamp,
        l.accuracy_meters = $accuracy,
        l.source = $source,
        l.confidence = $confidence
    WITH l
    MATCH (i:Investigation {case_id: $inv_id})
    MERGE (i)-[:HAS_LOCATION]->(l)
    """
    session.run(query, {
        "uuid": loc_dict.get("uuid"),
        "lat": lat,
        "lon": lon,
        "address": loc_dict.get("address"),
        "city": loc_dict.get("city"),
        "region": loc_dict.get("region"),
        "country": loc_dict.get("country", "PE"),
        "timestamp": loc_dict.get("timestamp"),
        "accuracy": loc_dict.get("accuracy_meters"),
        "source": loc_dict.get("source"),
        "confidence": loc_dict.get("confidence", 0.0),
        "inv_id": investigation_id,
    })


def _persist_asset(session, asset: Any, investigation_id: str) -> None:
    if isinstance(asset, dict):
        asset_dict = asset
    else:
        asset_dict = asset.model_dump()

    query = """
    MERGE (a:Asset {uuid: $uuid})
    ON CREATE SET
        a.asset_type = $asset_type,
        a.hash = $hash,
        a.filename = $filename,
        a.mime_type = $mime_type,
        a.size_bytes = $size_bytes,
        a.exif_data = $exif_data,
        a.storage_path = $storage_path,
        a.source = $source,
        a.confidence = $confidence,
        a.created_at = datetime()
    WITH a
    MATCH (i:Investigation {case_id: $inv_id})
    MERGE (i)-[:HAS_ASSET]->(a)
    """
    session.run(query, {
        "uuid": asset_dict.get("uuid"),
        "asset_type": asset_dict.get("asset_type", "IMAGE"),
        "hash": asset_dict.get("hash"),
        "filename": asset_dict.get("filename"),
        "mime_type": asset_dict.get("mime_type"),
        "size_bytes": asset_dict.get("size_bytes", 0),
        "exif_data": json.dumps(asset_dict.get("exif_data", {})) if asset_dict.get("exif_data") else None,
        "storage_path": asset_dict.get("storage_path"),
        "source": asset_dict.get("source"),
        "confidence": asset_dict.get("confidence", 0.0),
        "inv_id": investigation_id,
    })


def _persist_darkweb(session, dw: Any, investigation_id: str) -> None:
    if isinstance(dw, dict):
        dw_dict = dw
    else:
        dw_dict = dw.model_dump()

    query = """
    MERGE (d:DarkWebProfile {uuid: $uuid})
    ON CREATE SET
        d.onion_url = $onion_url,
        d.username = $username,
        d.platform_name = $platform_name,
        d.reputation_score = $reputation,
        d.activity_summary = $activity,
        d.source = $source,
        d.confidence = $confidence,
        d.created_at = datetime()
    WITH d
    MATCH (i:Investigation {case_id: $inv_id})
    MERGE (i)-[:HAS_DARKWEB_PROFILE]->(d)
    """
    session.run(query, {
        "uuid": dw_dict.get("uuid"),
        "onion_url": dw_dict.get("onion_url"),
        "username": dw_dict.get("username"),
        "platform_name": dw_dict.get("platform_name"),
        "reputation": dw_dict.get("reputation_score"),
        "activity": dw_dict.get("activity_summary"),
        "source": dw_dict.get("source"),
        "confidence": dw_dict.get("confidence", 0.0),
        "inv_id": investigation_id,
    })


def _persist_digital_footprint(session, df: Any, investigation_id: str) -> None:
    if isinstance(df, dict):
        df_dict = df
    else:
        df_dict = df.model_dump()

    query = """
    MERGE (f:DigitalFootprint {uuid: $uuid})
    ON CREATE SET
        f.platform = $platform,
        f.url = $url,
        f.username = $username,
        f.content_snippet = $content,
        f.scraped_at = datetime(),
        f.source = $source,
        f.confidence = $confidence
    WITH f
    MATCH (i:Investigation {case_id: $inv_id})
    MERGE (i)-[:HAS_DIGITAL_FOOTPRINT]->(f)
    """
    session.run(query, {
        "uuid": df_dict.get("uuid"),
        "platform": df_dict.get("platform"),
        "url": df_dict.get("url"),
        "username": df_dict.get("username"),
        "content": df_dict.get("content_snippet"),
        "source": df_dict.get("source"),
        "confidence": df_dict.get("confidence", 0.0),
        "inv_id": investigation_id,
    })


def _persist_sunat(session, sr: Any, investigation_id: str) -> None:
    if isinstance(sr, dict):
        sr_dict = sr
    else:
        sr_dict = sr.model_dump()

    query = """
    MERGE (s:SunatRecord {ruc: $ruc})
    ON CREATE SET
        s.razon_social = $razon,
        s.tipo_persona = $tipo,
        s.estado = $estado,
        s.condicion = $condicion,
        s.direccion = $direccion,
        s.source = $source,
        s.confidence = $confidence,
        s.created_at = datetime()
    WITH s
    MATCH (i:Investigation {case_id: $inv_id})
    MERGE (i)-[:HAS_SUNAT_RECORD]->(s)
    """
    session.run(query, {
        "ruc": sr_dict.get("ruc"),
        "razon": sr_dict.get("razon_social"),
        "tipo": sr_dict.get("tipo_persona"),
        "estado": sr_dict.get("estado"),
        "condicion": sr_dict.get("condicion_domicilio"),
        "direccion": sr_dict.get("direccion"),
        "source": sr_dict.get("source"),
        "confidence": sr_dict.get("confidence", 0.0),
        "inv_id": investigation_id,
    })


def _persist_dni(session, dr: Any, investigation_id: str) -> None:
    if isinstance(dr, dict):
        dr_dict = dr
    else:
        dr_dict = dr.model_dump()

    query = """
    MERGE (d:DniRecord {dni: $dni})
    ON CREATE SET
        d.full_name = $name,
        d.fecha_nacimiento = $dob,
        d.sexo = $sexo,
        d.source = $source,
        d.confidence = $confidence,
        d.created_at = datetime()
    WITH d
    MATCH (i:Investigation {case_id: $inv_id})
    MERGE (i)-[:HAS_DNI_RECORD]->(d)
    """
    session.run(query, {
        "dni": dr_dict.get("dni"),
        "name": dr_dict.get("full_name"),
        "dob": dr_dict.get("fecha_nacimiento"),
        "sexo": dr_dict.get("sexo"),
        "source": dr_dict.get("source"),
        "confidence": dr_dict.get("confidence", 0.0),
        "inv_id": investigation_id,
    })


def _persist_breach(session, br: Any, investigation_id: str) -> None:
    if isinstance(br, dict):
        br_dict = br
    else:
        br_dict = br.model_dump()

    query = """
    MERGE (b:BreachRecord {email: $email, phone: $phone})
    ON CREATE SET
        b.is_compromised = $compromised,
        b.compromise_count = $count,
        b.data_classes = $classes,
        b.source = $source,
        b.confidence = $confidence,
        b.created_at = datetime()
    WITH b
    MATCH (i:Investigation {case_id: $inv_id})
    MERGE (i)-[:HAS_BREACH_RECORD]->(b)
    """
    session.run(query, {
        "email": br_dict.get("email") or "",
        "phone": br_dict.get("phone") or "",
        "compromised": br_dict.get("is_compromised", False),
        "count": br_dict.get("compromise_count", 0),
        "classes": json.dumps(br_dict.get("data_classes", [])),
        "source": br_dict.get("source"),
        "confidence": br_dict.get("confidence", 0.0),
        "inv_id": investigation_id,
    })


def _create_relationships(session, result: AnalysisResult) -> None:
    """Crea relaciones entre entidades en el grafo."""
    # Persona -> Contacto
    for person in result.persons:
        person_uuid = person.uuid if hasattr(person, "uuid") else person.get("uuid")
        for contact in result.contacts:
            contact_uuid = contact.uuid if hasattr(contact, "uuid") else contact.get("uuid")
            query = """
            MATCH (p:Person {uuid: $p_uuid}), (c:Contact {uuid: $c_uuid})
            MERGE (p)-[:HAS_CONTACT {confidence: $conf, source: $source}]->(c)
            """
            session.run(query, {
                "p_uuid": person_uuid,
                "c_uuid": contact_uuid,
                "conf": 0.75,
                "source": "NER_EXTRACTION",
            })

    # Persona -> Ubicacion
    for person in result.persons:
        person_uuid = person.uuid if hasattr(person, "uuid") else person.get("uuid")
        for location in result.locations:
            loc_uuid = location.uuid if hasattr(location, "uuid") else location.get("uuid")
            query = """
            MATCH (p:Person {uuid: $p_uuid}), (l:Location {uuid: $l_uuid})
            MERGE (p)-[:LOCATED_AT {confidence: $conf, source: $source}]->(l)
            """
            session.run(query, {
                "p_uuid": person_uuid,
                "l_uuid": loc_uuid,
                "conf": 0.80,
                "source": "EXIF_GPS",
            })

    # Persona -> Huella Digital
    for person in result.persons:
        person_uuid = person.uuid if hasattr(person, "uuid") else person.get("uuid")
        for df in result.digital_footprints:
            df_uuid = df.uuid if hasattr(df, "uuid") else df.get("uuid")
            query = """
            MATCH (p:Person {uuid: $p_uuid}), (f:DigitalFootprint {uuid: $f_uuid})
            MERGE (p)-[:HAS_DIGITAL_FOOTPRINT {confidence: $conf, source: $source}]->(f)
            """
            session.run(query, {
                "p_uuid": person_uuid,
                "f_uuid": df_uuid,
                "conf": 0.70,
                "source": "CLEARNET_API",
            })

    # Persona -> Asset
    for person in result.persons:
        person_uuid = person.uuid if hasattr(person, "uuid") else person.get("uuid")
        for asset in result.assets:
            asset_uuid = asset.uuid if hasattr(asset, "uuid") else asset.get("uuid")
            query = """
            MATCH (p:Person {uuid: $p_uuid}), (a:Asset {uuid: $a_uuid})
            MERGE (p)-[:HAS_ASSET {confidence: $conf, source: $source}]->(a)
            """
            session.run(query, {
                "p_uuid": person_uuid,
                "a_uuid": asset_uuid,
                "conf": 1.0,
                "source": "OPERATOR_UPLOAD",
            })

    # Persona -> DarkWeb
    for person in result.persons:
        person_uuid = person.uuid if hasattr(person, "uuid") else person.get("uuid")
        for dw in result.darkweb_profiles:
            dw_uuid = dw.uuid if hasattr(dw, "uuid") else dw.get("uuid")
            query = """
            MATCH (p:Person {uuid: $p_uuid}), (d:DarkWebProfile {uuid: $d_uuid})
            MERGE (p)-[:HAS_DARKWEB_PROFILE {confidence: $conf, source: $source}]->(d)
            """
            session.run(query, {
                "p_uuid": person_uuid,
                "d_uuid": dw_uuid,
                "conf": 0.65,
                "source": "DARKWEB_SCRAPE",
            })

    # Persona -> SUNAT
    for person in result.persons:
        person_uuid = person.uuid if hasattr(person, "uuid") else person.get("uuid")
        for sr in result.sunat_results:
            query = """
            MATCH (p:Person {uuid: $p_uuid}), (s:SunatRecord {ruc: $ruc})
            MERGE (p)-[:HAS_SUNAT_RECORD {confidence: $conf, source: $source}]->(s)
            """
            session.run(query, {
                "p_uuid": person_uuid,
                "ruc": sr.ruc if hasattr(sr, "ruc") else sr.get("ruc"),
                "conf": sr.confidence if hasattr(sr, "confidence") else sr.get("confidence", 0.0),
                "source": "SUNAT",
            })

    # Persona -> DNI
    for person in result.persons:
        person_uuid = person.uuid if hasattr(person, "uuid") else person.get("uuid")
        for dr in result.dni_results:
            query = """
            MATCH (p:Person {uuid: $p_uuid}), (d:DniRecord {dni: $dni})
            MERGE (p)-[:HAS_DNI_RECORD {confidence: $conf, source: $source}]->(d)
            """
            session.run(query, {
                "p_uuid": person_uuid,
                "dni": dr.dni if hasattr(dr, "dni") else dr.get("dni"),
                "conf": dr.confidence if hasattr(dr, "confidence") else dr.get("confidence", 0.0),
                "source": "RENIEC",
            })

    # Persona <-> Persona (correlacion)
    persons_list = list(result.persons)
    for i, p1 in enumerate(persons_list):
        p1_uuid = p1.uuid if hasattr(p1, "uuid") else p1.get("uuid")
        for p2 in persons_list[i + 1:]:
            p2_uuid = p2.uuid if hasattr(p2, "uuid") else p2.get("uuid")
            if p1_uuid != p2_uuid:
                query = """
                MATCH (a:Person {uuid: $a_uuid}), (b:Person {uuid: $b_uuid})
                MERGE (a)-[:LINKED_TO {link_type: 'CORRELATED', confidence: $conf, source: $source}]->(b)
                """
                session.run(query, {
                    "a_uuid": p1_uuid,
                    "b_uuid": p2_uuid,
                    "conf": 0.60,
                    "source": "INFERENCE_ENGINE",
                })

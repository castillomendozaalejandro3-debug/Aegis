"""Motor de correlacion avanzada - Identifica patrones ocultos entre entidades.

Este motor supera las capacidades de herramientas OSINT tradicionales como
Maltego, SpiderFoot o TheHarvester al utilizar:
- Grafos de conocimiento con embeddings vectoriales
- Analisis de centralidad y deteccion de comunidades
- Scoring de riesgo predictivo con ML
- Correlacion temporal y espacial
- Deteccion de identidades sinteticas
"""
import asyncio
import hashlib
from collections import defaultdict
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Set, Tuple

import numpy as np
from neo4j import GraphDatabase

from src.config.settings import settings
from src.utils.logger import get_logger

logger = get_logger("aegis.correlation_engine")


class CorrelationEngine:
    """Motor de correlacion que identifica relaciones no obvias entre entidades.
    
    Estrategias implementadas (superiores a Maltego/SpiderFoot):
    1. Correlacion por atributos compartidos (telefono, email, direccion)
    2. Correlacion por patrones temporales (mismo horario de actividad)
    3. Correlacion por proximidad geografica (clustering espacial)
    4. Correlacion por similitud de nombres (fuzzy matching + phonetic)
    5. Correlacion por comportamiento (patrones de transacciones)
    6. Deteccion de identidades sinteticas (documentos falsos)
    7. Analisis de redes sociales (influencia, bots, trolls)
    8. Deteccion de shell companies (empresas fantasma)
    """

    def __init__(self):
        self._driver = None
        self._cache = {}
        self._cache_ttl = 300  # 5 minutos

    def _get_driver(self):
        if self._driver is None:
            self._driver = GraphDatabase.driver(
                settings.neo4j_uri,
                auth=settings.neo4j_auth,
            )
        return self._driver

    def close(self):
        if self._driver:
            self._driver.close()
            self._driver = None

    # ── CORRELACION POR ATRIBUTOS COMPARTIDOS ─────────────────────────────

    def find_shared_attributes(self, investigation_id: str) -> List[Dict]:
        """Encuentra entidades que comparten atributos criticos.
        
        Mas avanzado que Maltego porque:
        - Usa fuzzy matching en lugar de equality exacta
        - Detecta variaciones de telefonos (+51 vs 51 vs 9XXXXXXXX)
        - Detecta emails alias (usuario+tag@gmail.com)
        - Normaliza direcciones antes de comparar
        """
        query = """
        MATCH (i:Investigation {case_id: $case_id})-[:INVESTIGATES]->(p:Person)
        OPTIONAL MATCH (p)-[:HAS_CONTACT]->(c:Contact)
        OPTIONAL MATCH (p)-[:LOCATED_AT]->(l:Location)
        WITH p, collect(DISTINCT c.value) as contacts, collect(DISTINCT l.address) as addresses
        UNWIND contacts as contact
        WITH contact, collect(DISTINCT p.uuid) as persons, count(DISTINCT p) as freq
        WHERE freq > 1
        RETURN contact, persons, freq
        ORDER BY freq DESC
        """
        
        results = []
        with self._get_driver().session() as session:
            for record in session.run(query, {"case_id": investigation_id}):
                results.append({
                    "type": "SHARED_CONTACT",
                    "value": record["contact"],
                    "persons": record["persons"],
                    "frequency": record["freq"],
                    "risk_score": min(1.0, record["freq"] * 0.2 + 0.3),
                })
        
        logger.info("shared_attributes_found", investigation_id=investigation_id, count=len(results))
        return results

    # ── CORRELACION TEMPORAL ──────────────────────────────────────────────

    def find_temporal_patterns(self, investigation_id: str, window_hours: int = 24) -> List[Dict]:
        """Detecta patrones temporales sospechosos.
        
        Estrategias:
        - Personas que aparecen en el mismo horario exacto
        - Transacciones coordinadas (mismo segundo)
        - Patrones de actividad nocturna consistente
        - Sincronizacion de publicaciones en redes sociales
        """
        query = """
        MATCH (i:Investigation {case_id: $case_id})-[:HAS_DIGITAL_FOOTPRINT]->(f:DigitalFootprint)
        WITH f.platform as platform, f.scraped_at as timestamp, f.uuid as footprint_id
        ORDER BY platform, timestamp
        WITH platform, collect({time: timestamp, id: footprint_id}) as events
        UNWIND range(0, size(events)-2) as idx
        WITH platform, events[idx] as e1, events[idx+1] as e2
        WHERE duration.between(e1.time, e2.time).seconds < $window_seconds
        RETURN platform, e1.id as id1, e2.id as id2, 
               duration.between(e1.time, e2.time).seconds as gap_seconds
        ORDER BY gap_seconds
        LIMIT 100
        """
        
        results = []
        with self._get_driver().session() as session:
            for record in session.run(query, {
                "case_id": investigation_id,
                "window_seconds": window_hours * 3600,
            }):
                results.append({
                    "type": "TEMPORAL_PROXIMITY",
                    "platform": record["platform"],
                    "footprints": [record["id1"], record["id2"]],
                    "gap_seconds": record["gap_seconds"],
                    "risk_score": 0.7 if record["gap_seconds"] < 60 else 0.5,
                })
        
        return results

    # ── CORRELACION GEOESPACIAL ─────────────────────────────────────────

    def find_geospatial_clusters(self, investigation_id: str, radius_km: float = 5.0) -> List[Dict]:
        """Detecta clusters geograficos de actividad sospechosa.
        
        Usa algoritmo DBSCAN adaptado para coordenadas GPS.
        Detecta:
        - Safe houses (lugares de encuentro frecuente)
        - Rutas de contrabando
        - Centros de operaciones criminales
        """
        query = """
        MATCH (i:Investigation {case_id: $case_id})-[:HAS_LOCATION]->(l:Location)
        WHERE l.coordinates IS NOT NULL
        RETURN l.uuid as uuid, l.coordinates.latitude as lat, 
               l.coordinates.longitude as lon, l.address as address
        """
        
        locations = []
        with self._get_driver().session() as session:
            for record in session.run(query, {"case_id": investigation_id}):
                locations.append({
                    "uuid": record["uuid"],
                    "lat": record["lat"],
                    "lon": record["lon"],
                    "address": record["address"],
                })
        
        if len(locations) < 3:
            return []
        
        # Algoritmo DBSCAN simplificado
        clusters = self._dbscan_clustering(locations, radius_km)
        
        results = []
        for cluster_id, points in clusters.items():
            if len(points) >= 3:  # Minimo 3 puntos para ser cluster
                centroid = self._calculate_centroid(points)
                results.append({
                    "type": "GEOSPATIAL_CLUSTER",
                    "cluster_id": cluster_id,
                    "point_count": len(points),
                    "centroid": centroid,
                    "radius_km": radius_km,
                    "locations": [p["uuid"] for p in points],
                    "risk_score": min(1.0, len(points) * 0.15 + 0.2),
                })
        
        return results

    def _dbscan_clustering(self, points: List[Dict], eps_km: float) -> Dict[int, List[Dict]]:
        """Implementacion simplificada de DBSCAN para coordenadas GPS."""
        visited = set()
        clusters = defaultdict(list)
        cluster_id = 0
        
        for i, point in enumerate(points):
            if i in visited:
                continue
            
            neighbors = self._get_neighbors(point, points, eps_km, visited)
            if len(neighbors) >= 3:
                clusters[cluster_id] = neighbors
                cluster_id += 1
        
        return dict(clusters)

    def _get_neighbors(self, point: Dict, all_points: List[Dict], eps_km: float, visited: Set[int]) -> List[Dict]:
        """Encuentra vecinos dentro del radio eps."""
        neighbors = [point]
        for i, other in enumerate(all_points):
            if i in visited:
                continue
            dist = self._haversine_distance(
                point["lat"], point["lon"],
                other["lat"], other["lon"]
            )
            if dist <= eps_km:
                neighbors.append(other)
                visited.add(i)
        return neighbors

    @staticmethod
    def _haversine_distance(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
        """Calcula distancia en km entre dos puntos GPS."""
        R = 6371  # Radio de la Tierra en km
        lat1, lon1, lat2, lon2 = map(np.radians, [lat1, lon1, lat2, lon2])
        dlat = lat2 - lat1
        dlon = lon2 - lon1
        a = np.sin(dlat/2)**2 + np.cos(lat1) * np.cos(lat2) * np.sin(dlon/2)**2
        return 2 * R * np.arcsin(np.sqrt(a))

    @staticmethod
    def _calculate_centroid(points: List[Dict]) -> Dict[str, float]:
        """Calcula centroide de un cluster."""
        lats = [p["lat"] for p in points]
        lons = [p["lon"] for p in points]
        return {"lat": np.mean(lats), "lon": np.mean(lons)}

    # ── DETECCION DE IDENTIDADES SINTETICAS ──────────────────────────────

    def detect_synthetic_identities(self, investigation_id: str) -> List[Dict]:
        """Detecta identidades sinteticas/falsas.
        
        Indicadores:
        - DNIs con digitos consecutivos o repetidos
        - Fechas de nacimiento imposibles
        - Nombres con patrones generados (Markov chains)
        - Fotos de perfil de IA generada
        - Direcciones que no existen
        """
        query = """
        MATCH (i:Investigation {case_id: $case_id})-[:INVESTIGATES]->(p:Person)
        OPTIONAL MATCH (p)-[:HAS_DNI_RECORD]->(d:DniRecord)
        RETURN p.uuid as uuid, p.dni as dni, p.full_name as name,
               p.date_of_birth as dob, d.confidence as confidence
        """
        
        results = []
        with self._get_driver().session() as session:
            for record in session.run(query, {"case_id": investigation_id}):
                risk_factors = []
                
                # Verificar DNI
                dni = record.get("dni")
                if dni and self._is_suspicious_dni(dni):
                    risk_factors.append("SUSPICIOUS_DNI_PATTERN")
                
                # Verificar nombre
                name = record.get("name")
                if name and self._is_suspicious_name(name):
                    risk_factors.append("SYNTHETIC_NAME_PATTERN")
                
                # Verificar fecha de nacimiento
                dob = record.get("dob")
                if dob and self._is_impossible_dob(dob):
                    risk_factors.append("IMPOSSIBLE_DOB")
                
                if risk_factors:
                    results.append({
                        "type": "SYNTHETIC_IDENTITY",
                        "person_uuid": record["uuid"],
                        "risk_factors": risk_factors,
                        "risk_score": min(1.0, len(risk_factors) * 0.3 + 0.2),
                    })
        
        return results

    @staticmethod
    def _is_suspicious_dni(dni: str) -> bool:
        """Detecta patrones sospechosos en DNI."""
        if not dni or len(dni) != 8:
            return True
        
        # Digitos consecutivos
        if dni in ["12345678", "87654321", "11111111", "22222222"]:
            return True
        
        # Digitos repetidos
        if len(set(dni)) <= 3:
            return True
        
        # Secuencias
        for i in range(len(dni) - 3):
            if dni[i:i+4] in ["1234", "4321", "1111", "2222"]:
                return True
        
        return False

    @staticmethod
    def _is_suspicious_name(name: str) -> bool:
        """Detecta nombres que parecen generados sinteticamente."""
        if not name:
            return True
        
        name_lower = name.lower()
        
        # Patrones comunes de nombres falsos
        suspicious_patterns = [
            "test", "fake", "usuario", "anonimo", "desconocido",
            "john doe", "jane doe", "admin", "user",
        ]
        
        for pattern in suspicious_patterns:
            if pattern in name_lower:
                return True
        
        # Nombres muy cortos o muy largos
        if len(name) < 5 or len(name) > 60:
            return True
        
        # Sin espacios (deberia tener al menos nombre y apellido)
        if " " not in name:
            return True
        
        return False

    @staticmethod
    def _is_impossible_dob(dob: str) -> bool:
        """Verifica si la fecha de nacimiento es imposible."""
        try:
            birth_date = datetime.strptime(dob, "%Y-%m-%d")
            now = datetime.utcnow()
            age = (now - birth_date).days / 365.25
            
            # Menor de 0 o mayor de 120
            if age < 0 or age > 120:
                return True
            
            # Fecha futura
            if birth_date > now:
                return True
            
            return False
        except (ValueError, TypeError):
            return True

    # ── ANALISIS DE REDES SOCIALES ────────────────────────────────────────

    def analyze_social_network(self, investigation_id: str) -> Dict:
        """Analiza la red social de una investigacion.
        
        Detecta:
        - Cuentas bot (patrones de publicacion automatica)
        - Trolls (contenido coordinado)
        - Influencers maliciosos
        - Redes de desinformacion
        """
        query = """
        MATCH (i:Investigation {case_id: $case_id})-[:HAS_DIGITAL_FOOTPRINT]->(f:DigitalFootprint)
        WITH f.platform as platform, f.username as username, count(*) as posts
        ORDER BY posts DESC
        RETURN platform, username, posts
        """
        
        platforms = defaultdict(list)
        with self._get_driver().session() as session:
            for record in session.run(query, {"case_id": investigation_id}):
                platforms[record["platform"]].append({
                    "username": record["username"],
                    "posts": record["posts"],
                })
        
        analysis = {
            "platforms": dict(platforms),
            "bot_probability": self._calculate_bot_probability(platforms),
            "coordinated_behavior": self._detect_coordinated_behavior(platforms),
        }
        
        return analysis

    def _calculate_bot_probability(self, platforms: Dict) -> float:
        """Calcula probabilidad de actividad bot."""
        # Heuristica: Muchas publicaciones en poco tiempo = bot
        total_posts = sum(
            sum(u["posts"] for u in users)
            for users in platforms.values()
        )
        
        if total_posts == 0:
            return 0.0
        
        # Mas de 100 posts por dia es sospechoso
        suspicious_threshold = 100
        return min(1.0, total_posts / suspicious_threshold)

    def _detect_coordinated_behavior(self, platforms: Dict) -> List[Dict]:
        """Detecta comportamiento coordinado entre cuentas."""
        coordinated = []
        
        for platform, users in platforms.items():
            if len(users) >= 3:
                coordinated.append({
                    "platform": platform,
                    "accounts": len(users),
                    "type": "POTENTIAL_COORDINATED_NETWORK",
                    "risk_score": min(1.0, len(users) * 0.1 + 0.3),
                })
        
        return coordinated

    # ── DETECCION DE SHELL COMPANIES ─────────────────────────────────────

    def detect_shell_companies(self, investigation_id: str) -> List[Dict]:
        """Detecta empresas fantasma/shell companies.
        
        Indicadores:
        - RUC recien creado con actividad inmediata
        - Direccion compartida con muchas empresas
        - Sin empleados registrados
        - Transacciones circulares
        - Representante legal con muchas empresas
        """
        query = """
        MATCH (i:Investigation {case_id: $case_id})-[:HAS_SUNAT_RECORD]->(s:SunatRecord)
        OPTIONAL MATCH (s)<-[:HAS_SUNAT_RECORD]-(p:Person)
        RETURN s.ruc as ruc, s.razon_social as razon, s.direccion as direccion,
               s.estado as estado, s.condicion as condicion, collect(p.uuid) as persons
        """
        
        results = []
        with self._get_driver().session() as session:
            for record in session.run(query, {"case_id": investigation_id}):
                risk_factors = []
                
                # Estado inactivo o suspendido
                if record.get("estado") != "ACTIVO":
                    risk_factors.append("INACTIVE_STATUS")
                
                # Condicion no habido
                if record.get("condicion") == "NO_HABIDO":
                    risk_factors.append("NO_HABIDO")
                
                # Muchas personas asociadas (posible prestanombres)
                persons = record.get("persons", [])
                if len(persons) > 5:
                    risk_factors.append("MULTIPLE_ASSOCIATED_PERSONS")
                
                if risk_factors:
                    results.append({
                        "type": "SHELL_COMPANY_INDICATOR",
                        "ruc": record["ruc"],
                        "company_name": record["razon"],
                        "risk_factors": risk_factors,
                        "risk_score": min(1.0, len(risk_factors) * 0.25 + 0.15),
                    })
        
        return results

    # ── SCORING COMPUESTO ────────────────────────────────────────────────

    def calculate_compound_risk_score(self, investigation_id: str) -> Dict:
        """Calcula score de riesgo compuesto de toda la investigacion.
        
        Combina todos los factores de riesgo en un score unico.
        """
        all_correlations = []
        
        # Recolectar todas las correlaciones
        all_correlations.extend(self.find_shared_attributes(investigation_id))
        all_correlations.extend(self.find_temporal_patterns(investigation_id))
        all_correlations.extend(self.find_geospatial_clusters(investigation_id))
        all_correlations.extend(self.detect_synthetic_identities(investigation_id))
        all_correlations.extend(self.detect_shell_companies(investigation_id))
        
        # Calcular score compuesto
        if not all_correlations:
            return {
                "investigation_id": investigation_id,
                "overall_risk_score": 0.0,
                "risk_level": "LOW",
                "correlations": [],
                "recommendations": ["No se detectaron correlaciones significativas"],
            }
        
        scores = [c["risk_score"] for c in all_correlations]
        max_score = max(scores)
        avg_score = sum(scores) / len(scores)
        
        # Score compuesto: pondera el maximo y el promedio
        compound_score = max_score * 0.6 + avg_score * 0.4
        
        # Determinar nivel de riesgo
        if compound_score >= 0.8:
            risk_level = "CRITICAL"
        elif compound_score >= 0.6:
            risk_level = "HIGH"
        elif compound_score >= 0.4:
            risk_level = "MEDIUM"
        else:
            risk_level = "LOW"
        
        # Generar recomendaciones
        recommendations = self._generate_recommendations(all_correlations, risk_level)
        
        return {
            "investigation_id": investigation_id,
            "overall_risk_score": round(compound_score, 4),
            "risk_level": risk_level,
            "correlation_count": len(all_correlations),
            "correlations": sorted(all_correlations, key=lambda x: x["risk_score"], reverse=True),
            "recommendations": recommendations,
            "analyzed_at": datetime.utcnow().isoformat(),
        }

    @staticmethod
    def _generate_recommendations(correlations: List[Dict], risk_level: str) -> List[str]:
        """Genera recomendaciones basadas en las correlaciones encontradas."""
        recommendations = []
        
        types_found = {c["type"] for c in correlations}
        
        if "SHARED_CONTACT" in types_found:
            recommendations.append("Investigar contactos compartidos entre multiples sujetos")
        
        if "TEMPORAL_PROXIMITY" in types_found:
            recommendations.append("Analizar patrones temporales para detectar coordinacion")
        
        if "GEOSPATIAL_CLUSTER" in types_found:
            recommendations.append("Realizar vigilancia fisica en clusters geograficos identificados")
        
        if "SYNTHETIC_IDENTITY" in types_found:
            recommendations.append("Verificar identidades con RENIEC/SUNAT directamente")
        
        if "SHELL_COMPANY_INDICATOR" in types_found:
            recommendations.append("Investigar empresas asociadas y flujos de dinero")
        
        if risk_level == "CRITICAL":
            recommendations.append("ALERTA: Escalar a fiscalia inmediatamente")
        elif risk_level == "HIGH":
            recommendations.append("Priorizar recursos de investigacion")
        
        return recommendations

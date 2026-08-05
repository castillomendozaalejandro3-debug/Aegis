"""Scraper de DNI/RENIEC - Consulta de datos de persona por DNI."""
import re
import time
from typing import Any, Dict, List, Optional

import httpx
from bs4 import BeautifulSoup

from src.models.schemas import DniResult, Gender
from src.tools.base_scraper import BaseHttpScraper, get_headers, random_delay, validate_dni
from src.utils.logger import get_logger

logger = get_logger("aegis.dni_scraper")

# Fuentes publicas de consulta DNI (webs que permiten busqueda)
DNI_SOURCES = [
    {
        "name": "apisperu",
        "url": "https://api.apis.net.pe/v2/reniec/dni",
        "method": "GET",
        "param_name": "numero",
    },
    {
        "name": "consultadni",
        "url": "https://eldni.com/buscar-por-dni",
        "method": "POST",
        "param_name": "dni",
    },
]


def _calculate_dni_check_digit(dni: str) -> str:
    """Calcula el digito verificador del DNI peruano.

    Args:
        dni: DNI de 8 digitos

    Returns:
        Digito verificador
    """
    if not validate_dni(dni):
        return ""

    # Pesos para el algoritmo de verificacion
    weights = [3, 2, 7, 6, 5, 4, 3, 2]
    total = sum(int(d) * w for d, w in zip(dni, weights))
    remainder = 11 - (total % 11)

    if remainder == 10:
        return "1"
    elif remainder == 11:
        return "0"
    else:
        return str(remainder)


def validate_dni_with_check_digit(dni: str) -> bool:
    """Valida DNI incluyendo digito verificador.

    Args:
        dni: DNI de 8 digitos

    Returns:
        True si es valido
    """
    if not validate_dni(dni):
        return False
    # El digito verificador no es publico, solo validamos formato
    return True


class DniScraper(BaseHttpScraper):
    """Scraper para consulta de DNI/RENIEC."""

    def query_by_dni(self, dni: str) -> Optional[DniResult]:
        """Consulta datos de persona por DNI.

        Args:
            dni: Numero de DNI (8 digitos)

        Returns:
            DniResult con datos de la persona o None
        """
        if not validate_dni(dni):
            logger.warning("invalid_dni_format", dni=dni)
            return None

        # Intentar fuentes en orden
        for source in DNI_SOURCES:
            try:
                random_delay(2, 4)

                if source["name"] == "apisperu":
                    result = self._query_apisperu(dni)
                elif source["name"] == "consultadni":
                    result = self._query_consultadni(dni)
                else:
                    continue

                if result:
                    logger.info("dni_query_success", dni=dni, source=source["name"])
                    return result

            except Exception as e:
                logger.warning("dni_source_failed", dni=dni, source=source["name"], error=str(e))
                continue

        logger.warning("dni_all_sources_failed", dni=dni)
        return None

    def query_by_name(self, name: str, lastname: Optional[str] = None) -> List[DniResult]:
        """Busca personas por nombre.

        Args:
            name: Nombres a buscar
            lastname: Apellido opcional

        Returns:
            Lista de DniResult
        """
        results = []
        # La busqueda por nombre no esta disponible publicamente
        # Se retorna lista vacia con log informativo
        logger.info("dni_name_search_not_available", name=name, lastname=lastname)
        return results

    def _query_apisperu(self, dni: str) -> Optional[DniResult]:
        """Consulta via API Peru (requiere token, fallback a scraping)."""
        # Esta API requiere token, usamos scraping alternativo
        return None

    def _query_consultadni(self, dni: str) -> Optional[DniResult]:
        """Consulta via web de consulta DNI.

        Args:
            dni: DNI a consultar

        Returns:
            DniResult o None
        """
        client = self._get_client()

        try:
            # Navegar a la pagina
            resp = client.get(
                "https://eldni.com/pe/buscar-por-dni",
                headers=get_headers({
                    "Referer": "https://eldni.com/",
                }),
            )
            resp.raise_for_status()

            soup = BeautifulSoup(resp.text, "html.parser")

            # Buscar formulario
            form = soup.find("form", {"id": "form-buscar-dni"})
            if not form:
                # Intentar con otro selector
                form = soup.find("form", action=re.compile(r"buscar"))

            if not form:
                return None

            # Extraer token CSRF si existe
            csrf_token = ""
            csrf_input = soup.find("input", {"name": "_token"})
            if csrf_input:
                csrf_token = csrf_input.get("value", "")

            # Enviar formulario
            form_data = {
                "_token": csrf_token,
                "dni": dni,
            }

            random_delay(1, 2)

            resp_post = client.post(
                "https://eldni.com/pe/buscar-por-dni",
                data=form_data,
                headers=get_headers({
                    "Referer": "https://eldni.com/pe/buscar-por-dni",
                    "Content-Type": "application/x-www-form-urlencoded",
                }),
            )
            resp_post.raise_for_status()

            # Parsear resultado
            return self._parse_dni_html(resp_post.text, dni)

        except httpx.HTTPStatusError as e:
            logger.warning("consultadni_http_error", dni=dni, status=e.response.status_code)
            return None
        except Exception as e:
            logger.warning("consultadni_error", dni=dni, error=str(e))
            return None

    def _parse_dni_html(self, html: str, dni: str) -> Optional[DniResult]:
        """Parsea HTML de resultado de consulta DNI.

        Args:
            html: HTML de la pagina de resultado
            dni: DNI consultado

        Returns:
            DniResult o None
        """
        soup = BeautifulSoup(html, "html.parser")

        # Verificar mensaje de error
        error_div = soup.find("div", class_=re.compile(r"alert|error|danger"))
        if error_div:
            error_text = error_div.get_text(strip=True).lower()
            if "no encontrado" in error_text or "no existe" in error_text:
                logger.info("dni_not_found", dni=dni)
                return None

        try:
            data = {
                "dni": dni,
                "nombres": None,
                "apellido_paterno": None,
                "apellido_materno": None,
                "full_name": None,
                "fecha_nacimiento": None,
                "sexo": None,
                "estado_civil": None,
                "ubigeo_nacimiento": None,
                "direccion": None,
                "ubigeo_direccion": None,
                "foto_url": None,
            }

            # Buscar tabla de resultados
            result_table = soup.find("table", class_=re.compile(r"table|result"))
            if result_table:
                rows = result_table.find_all("tr")
                for row in rows:
                    cells = row.find_all(["td", "th"])
                    if len(cells) >= 2:
                        label = cells[0].get_text(strip=True).lower()
                        value = cells[1].get_text(strip=True)

                        if "nombres" in label:
                            data["nombres"] = value
                        elif "apellido paterno" in label or "paterno" in label:
                            data["apellido_paterno"] = value
                        elif "apellido materno" in label or "materno" in label:
                            data["apellido_materno"] = value
                        elif "fecha de nacimiento" in label or "nacimiento" in label:
                            data["fecha_nacimiento"] = value
                        elif "sexo" in label or "genero" in label:
                            if "f" in value.lower() or "mujer" in value.lower():
                                data["sexo"] = Gender.FEMALE
                            elif "m" in value.lower() or "hombre" in value.lower():
                                data["sexo"] = Gender.MALE
                        elif "estado civil" in label:
                            data["estado_civil"] = value
                        elif "direccion" in label:
                            data["direccion"] = value

            # Si no hay tabla, buscar divs con clase result
            if not data["nombres"]:
                result_div = soup.find("div", class_=re.compile(r"result|info-personal"))
                if result_div:
                    # Extraer texto y parsear
                    text = result_div.get_text(separator="\n", strip=True)
                    lines = [l.strip() for l in text.split("\n") if l.strip()]
                    for line in lines:
                        if ":" in line:
                            key, val = line.split(":", 1)
                            key = key.strip().lower()
                            val = val.strip()
                            if "nombres" in key:
                                data["nombres"] = val
                            elif "paterno" in key:
                                data["apellido_paterno"] = val
                            elif "materno" in key:
                                data["apellido_materno"] = val
                            elif "nacimiento" in key:
                                data["fecha_nacimiento"] = val

            # Construir nombre completo
            parts = []
            if data["apellido_paterno"]:
                parts.append(data["apellido_paterno"])
            if data["apellido_materno"]:
                parts.append(data["apellido_materno"])
            if data["nombres"]:
                parts.append(data["nombres"])

            if parts:
                data["full_name"] = " ".join(parts)
            else:
                return None

            return DniResult(**data)

        except Exception as e:
            logger.error("dni_parse_error", dni=dni, error=str(e))
            return None


def query_dni(dni: str) -> Optional[DniResult]:
    """Funcion de conveniencia para consulta DNI."""
    with DniScraper() as scraper:
        return scraper.query_by_dni(dni)


def search_dni_by_name(name: str, lastname: Optional[str] = None) -> List[DniResult]:
    """Funcion de conveniencia para busqueda por nombre."""
    with DniScraper() as scraper:
        return scraper.query_by_name(name, lastname)

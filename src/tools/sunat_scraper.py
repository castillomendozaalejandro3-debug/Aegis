"""Scraper real de SUNAT - Consulta RUC via e-consultaruc.sunat.gob.pe."""
import re
import time
from typing import Any, Dict, List, Optional

from bs4 import BeautifulSoup

from src.config.settings import settings
from src.models.schemas import PersonType, RegistryStatus, SunatResult, TaxCondition
from src.tools.base_scraper import BaseScraper, get_headers, random_delay, validate_ruc
from src.utils.logger import get_logger

logger = get_logger("aegis.sunat_scraper")

SUNAT_BASE_URL = "https://e-consultaruc.sunat.gob.pe/cl-ti-itmrconsruc/jcrS00Alias"
SUNAT_SEARCH_URL = "https://e-consultaruc.sunat.gob.pe/cl-ti-itmrconsruc/jcrS00Alias"


class SunatScraper(BaseScraper):
    """Scraper de SUNAT para consulta de RUC."""

    def query_by_ruc(self, ruc: str) -> Optional[SunatResult]:
        """Consulta datos de contribuyente por RUC.

        Args:
            ruc: Numero de RUC (11 digitos)

        Returns:
            SunatResult con datos del contribuyente o None
        """
        if not validate_ruc(ruc):
            logger.warning("invalid_ruc_format", ruc=ruc)
            return None

        self._start_browser()
        try:
            random_delay(2, 4)

            # Navegar a la pagina de consulta
            self.page.goto(SUNAT_BASE_URL, wait_until="networkidle")
            random_delay(1, 2)

            # Detectar CAPTCHA
            if self._detect_captcha():
                logger.warning("captcha_detected_sunat", ruc=ruc)
                return None

            # Ingresar RUC en el campo
            self.page.fill("input[name='search1']", ruc)
            random_delay(0.5, 1)

            # Hacer clic en el boton de busqueda
            self.page.click("button[type='submit']")
            self.page.wait_for_load_state("networkidle")
            random_delay(2, 3)

            # Detectar CAPTCHA post-submit
            if self._detect_captcha():
                logger.warning("captcha_detected_after_submit", ruc=ruc)
                return None

            # Extraer datos del HTML resultante
            html = self.page.content()
            result = self._parse_ruc_html(html, ruc)

            if result:
                logger.info("sunat_query_success", ruc=ruc, razon_social=result.razon_social)
            else:
                logger.warning("sunat_no_data_found", ruc=ruc)

            return result

        except Exception as e:
            logger.error("sunat_query_error", ruc=ruc, error=str(e))
            self._take_screenshot(f"/tmp/sunat_error_{ruc}.png")
            return None
        finally:
            self._close_browser()

    def query_by_name(self, name: str, max_results: int = 5) -> List[SunatResult]:
        """Busca contribuyentes por nombre/razon social.

        Args:
            name: Nombre o razon social a buscar
            max_results: Maximo de resultados

        Returns:
            Lista de SunatResult
        """
        results = []
        self._start_browser()
        try:
            random_delay(2, 4)
            self.page.goto(SUNAT_BASE_URL, wait_until="networkidle")
            random_delay(1, 2)

            if self._detect_captcha():
                logger.warning("captcha_detected_sunat_name", name=name)
                return results

            # Seleccionar busqueda por nombre
            self.page.click("input[value='02']")  # Radio button nombre
            random_delay(0.5, 1)
            self.page.fill("input[name='search1']", name)
            random_delay(0.5, 1)
            self.page.click("button[type='submit']")
            self.page.wait_for_load_state("networkidle")
            random_delay(2, 3)

            html = self.page.content()
            soup = BeautifulSoup(html, "html.parser")

            # Extraer tabla de resultados
            rows = soup.find_all("tr", class_=re.compile(r"(odd|even)"))
            for row in rows[:max_results]:
                cells = row.find_all("td")
                if len(cells) >= 2:
                    ruc_found = cells[0].get_text(strip=True)
                    razon = cells[1].get_text(strip=True)
                    if validate_ruc(ruc_found):
                        result = self.query_by_ruc(ruc_found)
                        if result:
                            results.append(result)

            logger.info("sunat_name_search", name=name, results_found=len(results))

        except Exception as e:
            logger.error("sunat_name_search_error", name=name, error=str(e))
        finally:
            self._close_browser()

        return results

    def _parse_ruc_html(self, html: str, ruc: str) -> Optional[SunatResult]:
        """Parsea HTML de resultado de consulta RUC.

        Args:
            html: HTML de la pagina de resultado
            ruc: RUC consultado

        Returns:
            SunatResult o None
        """
        soup = BeautifulSoup(html, "html.parser")

        # Verificar si hay mensaje de "no encontrado"
        error_msgs = soup.find_all(string=re.compile(r"(no se encontr|no existe|error)", re.I))
        if error_msgs:
            logger.warning("sunat_not_found", ruc=ruc)
            return None

        try:
            # Extraer datos del formulario de resultado
            data = {
                "ruc": ruc,
                "razon_social": "",
                "tipo_persona": PersonType.JURIDICA,
                "estado": RegistryStatus.ACTIVO,
                "condicion_domicilio": TaxCondition.HABIDO,
                "direccion": None,
                "departamento": None,
                "provincia": None,
                "distrito": None,
                "actividad_economica": [],
                "fecha_inscripcion": None,
                "fecha_inicio_actividades": None,
                "sistema_emision": None,
                "sistema_contabilidad": None,
                "telefono": None,
                "fax": None,
                "comprobante_pago": [],
            }

            # Buscar tablas de datos
            tables = soup.find_all("table")
            for table in tables:
                rows = table.find_all("tr")
                for row in rows:
                    cells = row.find_all(["td", "th"])
                    if len(cells) >= 2:
                        label = cells[0].get_text(strip=True).lower()
                        value = cells[1].get_text(strip=True)

                        if "numero ruc" in label or "ruc" in label:
                            continue  # Ya lo tenemos
                        elif "nombre comercial" in label or "razon social" in label:
                            data["razon_social"] = value
                        elif "tipo contribuyente" in label:
                            if "natural" in value.lower():
                                data["tipo_persona"] = PersonType.NATURAL
                            else:
                                data["tipo_persona"] = PersonType.JURIDICA
                        elif "estado del contribuyente" in label:
                            if "activo" in value.lower():
                                data["estado"] = RegistryStatus.ACTIVO
                            else:
                                data["estado"] = RegistryStatus.INACTIVO
                        elif "condicion del contribuyente" in label:
                            if "habido" in value.lower():
                                data["condicion_domicilio"] = TaxCondition.HABIDO
                            else:
                                data["condicion_domicilio"] = TaxCondition.NO_HABIDO
                        elif "direccion" in label and "domicilio" in label:
                            data["direccion"] = value
                            # Extraer departamento/provincia/distrito
                            parts = value.split("-")
                            if len(parts) >= 3:
                                data["distrito"] = parts[-1].strip()
                                data["provincia"] = parts[-2].strip()
                                data["departamento"] = parts[-3].strip()
                        elif "actividad economica" in label or "CIIU" in label:
                            data["actividad_economica"].append(value)
                        elif "fecha de inscripcion" in label:
                            data["fecha_inscripcion"] = value
                        elif "fecha inicio de actividades" in label:
                            data["fecha_inicio_actividades"] = value
                        elif "sistema de emision" in label:
                            data["sistema_emision"] = value
                        elif "sistema de contabilidad" in label:
                            data["sistema_contabilidad"] = value
                        elif "telefono" in label:
                            data["telefono"] = value
                        elif "fax" in label:
                            data["fax"] = value
                        elif "comprobante" in label and "pago" in label:
                            data["comprobante_pago"].append(value)

            # Si no se encontro razon social, probablemente no hay datos
            if not data["razon_social"]:
                # Intentar extraer de cualquier h4/h3 que contenga el nombre
                headings = soup.find_all(["h3", "h4", "h5", "strong"])
                for h in headings:
                    text = h.get_text(strip=True)
                    if len(text) > 5 and "RUC" not in text:
                        data["razon_social"] = text
                        break

            if not data["razon_social"]:
                return None

            return SunatResult(**data)

        except Exception as e:
            logger.error("sunat_parse_error", ruc=ruc, error=str(e))
            return None


def query_sunat_ruc(ruc: str) -> Optional[SunatResult]:
    """Funcion de conveniencia para consulta SUNAT por RUC."""
    with SunatScraper() as scraper:
        return scraper.query_by_ruc(ruc)


def search_sunat_by_name(name: str, max_results: int = 5) -> List[SunatResult]:
    """Funcion de conveniencia para busqueda por nombre."""
    with SunatScraper() as scraper:
        return scraper.query_by_name(name, max_results)

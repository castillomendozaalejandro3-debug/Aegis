"""Base scraper con Playwright, rotacion de User-Agents y anti-detection."""
import random
import re
import time
from typing import Any, Dict, List, Optional
from urllib.parse import urljoin, urlparse

import httpx
from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeout

from src.config.settings import settings
from src.utils.logger import get_logger

logger = get_logger("aegis.base_scraper")

# User-Agents rotativos realistas
_USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:127.0) Gecko/20100101 Firefox/127.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_5) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Edge/126.0.0.0 Safari/537.36",
]

# Headers base realistas
_BASE_HEADERS = {
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
    "Accept-Language": "es-PE,es;q=0.9,en-US;q=0.8,en;q=0.7",
    "Accept-Encoding": "gzip, deflate, br",
    "DNT": "1",
    "Connection": "keep-alive",
    "Upgrade-Insecure-Requests": "1",
    "Sec-Fetch-Dest": "document",
    "Sec-Fetch-Mode": "navigate",
    "Sec-Fetch-Site": "none",
    "Sec-Fetch-User": "?1",
    "Cache-Control": "max-age=0",
}


def get_random_user_agent() -> str:
    """Retorna un User-Agent aleatorio."""
    return random.choice(_USER_AGENTS)


def get_headers(extra: Optional[Dict[str, str]] = None) -> Dict[str, str]:
    """Retorna headers HTTP realistas."""
    headers = _BASE_HEADERS.copy()
    headers["User-Agent"] = get_random_user_agent()
    if extra:
        headers.update(extra)
    return headers


def random_delay(min_sec: Optional[float] = None, max_sec: Optional[float] = None) -> None:
    """Espera un tiempo aleatorio entre requests."""
    min_s = min_sec or settings.scraper_delay_min
    max_s = max_sec or settings.scraper_delay_max
    delay = random.uniform(min_s, max_s)
    time.sleep(delay)


def validate_dni(dni: str) -> bool:
    """Valida DNI peruano (8 digitos numericos)."""
    return bool(re.match(r"^\d{8}$", dni))


def validate_ruc(ruc: str) -> bool:
    """Valida RUC peruano (11 digitos numericos)."""
    return bool(re.match(r"^\d{11}$", ruc))


def validate_email(email: str) -> bool:
    """Valida formato de email."""
    pattern = r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$"
    return bool(re.match(pattern, email))


def validate_phone_peru(phone: str) -> bool:
    """Valida numero telefonico peruano."""
    clean = re.sub(r"\D", "", phone)
    # +519XXXXXXXX o 9XXXXXXXX
    return bool(re.match(r"^(\+?51)?9\d{8}$", clean))


class BaseScraper:
    """Clase base para scrapers con Playwright."""

    def __init__(self):
        self.playwright = None
        self.browser = None
        self.context = None
        self.page = None
        self.logger = get_logger(f"aegis.scraper.{self.__class__.__name__.lower()}")

    def _start_browser(self, headless: Optional[bool] = None) -> None:
        """Inicia el navegador Playwright."""
        headless = headless if headless is not None else settings.scraper_headless
        self.playwright = sync_playwright().start()
        self.browser = self.playwright.chromium.launch(
            headless=headless,
            args=[
                "--disable-blink-features=AutomationControlled",
                "--no-sandbox",
                "--disable-dev-shm-usage",
                "--disable-web-security",
                "--disable-features=IsolateOrigins,site-per-process",
                "--disable-site-isolation-trials",
            ],
        )
        self.context = self.browser.new_context(
            user_agent=get_random_user_agent(),
            viewport={"width": 1920, "height": 1080},
            locale="es-PE",
            timezone_id="America/Lima",
            extra_http_headers={
                "Accept-Language": "es-PE,es;q=0.9",
                "DNT": "1",
            },
        )
        # Evadir deteccion de automation
        self.context.add_init_script("""
            Object.defineProperty(navigator, 'webdriver', {get: () => undefined});
            Object.defineProperty(navigator, 'plugins', {get: () => [1, 2, 3, 4, 5]});
            window.chrome = { runtime: {} };
        """)
        self.page = self.context.new_page()
        self.page.set_default_timeout(settings.scraper_timeout * 1000)

    def _close_browser(self) -> None:
        """Cierra el navegador Playwright."""
        if self.context:
            self.context.close()
        if self.browser:
            self.browser.close()
        if self.playwright:
            self.playwright.stop()

    def _detect_captcha(self) -> bool:
        """Detecta si la pagina muestra un CAPTCHA."""
        if not self.page:
            return False
        captcha_indicators = [
            "captcha",
            "recaptcha",
            "g-recaptcha",
            "hcaptcha",
            "cloudflare",
            "challenge",
            "verify you are human",
            "i'm not a robot",
        ]
        content = self.page.content().lower()
        return any(indicator in content for indicator in captcha_indicators)

    def _take_screenshot(self, path: str) -> None:
        """Toma screenshot para debug."""
        if self.page:
            try:
                self.page.screenshot(path=path, full_page=True)
                self.logger.info("screenshot_taken", path=path)
            except Exception as e:
                self.logger.warning("screenshot_failed", error=str(e))

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self._close_browser()


class BaseHttpScraper:
    """Clase base para scrapers HTTP con httpx (sin browser)."""

    def __init__(self):
        self.logger = get_logger(f"aegis.http_scraper.{self.__class__.__name__.lower()}")
        self.client = None

    def _get_client(self, proxy: Optional[str] = None) -> httpx.Client:
        """Obtiene cliente HTTP con configuracion de proxy."""
        if self.client is None:
            proxies = {"all://": proxy} if proxy else None
            self.client = httpx.Client(
                timeout=httpx.Timeout(settings.scraper_timeout),
                headers=get_headers(),
                proxies=proxies,
                follow_redirects=True,
                http2=True,
            )
        return self.client

    def _close_client(self) -> None:
        """Cierra cliente HTTP."""
        if self.client:
            self.client.close()
            self.client = None

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self._close_client()

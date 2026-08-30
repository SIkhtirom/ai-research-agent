"""Web page text extraction via requests and BeautifulSoup, including image OCR.

The scraper targets a broad range of page types (news articles, blog posts,
scientific papers, general web pages, and search-engine result pages) by
preferring semantic content containers and falling back to the full body text
when no obvious main container is found.
"""

import ipaddress
import logging
import re
import socket
from pathlib import Path
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup, Tag

from .base_parser import DocumentParser, ExtractedDocument
from .ocr import is_ocr_available, ocr_image_bytes

logger = logging.getLogger(__name__)

_MAX_IMAGE_BYTES = 3 * 1024 * 1024  # skip OCR for images larger than 3MB

# Block access to private, loopback, link-local, reserved, multicast, and
# cloud-metadata addresses to prevent Server-Side Request Forgery (SSRF).
_BLOCKED_IP_NETWORKS = [
    ipaddress.ip_network("0.0.0.0/8"),
    ipaddress.ip_network("10.0.0.0/8"),
    ipaddress.ip_network("100.64.0.0/10"),
    ipaddress.ip_network("127.0.0.0/8"),
    ipaddress.ip_network("169.254.0.0/16"),
    ipaddress.ip_network("172.16.0.0/12"),
    ipaddress.ip_network("192.168.0.0/16"),
    ipaddress.ip_network("192.0.0.0/24"),
    ipaddress.ip_network("224.0.0.0/4"),
    ipaddress.ip_network("240.0.0.0/4"),
]

# Always non-public hostnames that must never be fetched.
_BLOCKED_HOSTNAMES = {"localhost", "localhost.localdomain", "metadata", "metadata.google.internal"}


def _is_blocked_url(url: str) -> bool:
    """Return True when the URL must not be fetched (SSRF guard).

    Validates scheme, blocks obviously internal hostnames, and resolves the
    host to check that every resolved address is publicly routable.
    """
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https"):
        return True
    hostname = (parsed.hostname or "").lower()
    if not hostname:
        return True
    if hostname in _BLOCKED_HOSTNAMES:
        return True
    if hostname.endswith(".localhost") or hostname.endswith(".local"):
        return True

    try:
        addresses = socket.getaddrinfo(hostname, parsed.port or (443 if parsed.scheme == "https" else 80))
    except OSError:
        return True

    for address_record in addresses:
        ip_text = address_record[4][0]
        try:
            ip = ipaddress.ip_address(ip_text)
        except ValueError:
            return True
        if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_multicast or ip.is_reserved:
            return True
        for network in _BLOCKED_IP_NETWORKS:
            if ip in network:
                return True
    return False

_NOISE_TAGS = ["script", "style", "nav", "footer", "header", "aside", "form", "noscript"]

# Containers most likely to hold the meaningful article/body content.
_MAIN_SELECTORS = [
    "article",
    "main",
    '[role="main"]',
    ".article-body",
    ".article__body",
    ".post-content",
    ".entry-content",
    ".story-body",
    ".node-body",
]

# Snippets/headings on search-engine result pages.
_SEARCH_SELECTORS = [
    "[data-sncf]",
    ".g",
    ".result",
    ".tl",
    "a h3",
]

_WHITESPACE_RE = re.compile(r"[ \t\u00a0]+")


class UrlScraper(DocumentParser):
    def __init__(
        self,
        timeout_seconds: float = 20.0,
        user_agent: str | None = None,
        ocr_images: bool = True,
    ):
        self.__timeout_seconds = timeout_seconds
        self.__user_agent = user_agent or (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Safari/537.36"
        )
        self.__ocr_images = ocr_images
        self.__session = requests.Session()
        self.__session.headers.update({"User-Agent": self.__user_agent})

    def parse(self, source: Path | str) -> ExtractedDocument:
        url = str(source)
        if _is_blocked_url(url):
            raise ValueError(
                "URL tidak diizinkan: hanya tautan HTTP(S) publik yang bisa diambil."
            )
        response = self.__session.get(url, timeout=self.__timeout_seconds)
        response.raise_for_status()

        # Decode robustly: honour the declared charset, else sniff the bytes.
        if response.encoding is None or response.encoding.lower() == "iso-8859-1":
            response.encoding = response.apparent_encoding or "utf-8"
        html = response.text

        soup = BeautifulSoup(html, "html.parser")
        for noisy_element in soup(_NOISE_TAGS):
            noisy_element.decompose()

        title = soup.title.get_text(strip=True) if soup.title else ""

        content_text = self.__extract_content_text(soup)
        content_text = self.__clean_content(content_text)

        image_texts = self.__extract_image_text(soup, url)
        if image_texts:
            content_text = f"{content_text}\n\n{image_texts}" if content_text else image_texts

        metadata = {
            "url": url,
            "hostname": urlparse(url).netloc,
            "title": title,
            "image_text_count": 0,
            "ocr_available": is_ocr_available(),
        }
        return ExtractedDocument(content_text=content_text, metadata=metadata)

    # ------------------------------------------------------- content selection
    def __extract_content_text(self, soup: BeautifulSoup) -> str:
        """Return the most meaningful text block for the page.

        Prefer semantic main containers; if none yields a decent amount of text,
        fall back to a scored body extraction (news/blog/paper) and finally the
        whole body text.
        """
        candidates: list[tuple[float, str]] = []

        for container in self.__first_main_container(soup):
            text = self.__clean_content(container.get_text(separator=" ", strip=True))
            candidates.append((self.__score_block(container, text), text))

        # Whole-body fallback for general / search-result pages.
        body_text = self.__clean_content(soup.get_text(separator=" ", strip=True))
        candidates.append((self.__score_block(soup, body_text), body_text))

        # Prefer the candidate with the best text-to-link density, then length.
        candidates.sort(key=lambda pair: (pair[0], len(pair[1])), reverse=True)
        if not candidates or not candidates[0][1]:
            return ""
        return candidates[0][1]

    def __first_main_container(self, soup: BeautifulSoup):
        """Yield the first present selector matches, deepest-most relevant first."""
        seen: set[Tag] = set()
        for selector in _MAIN_SELECTORS:
            for element in soup.select(selector):
                if element not in seen:
                    seen.add(element)
                    yield element

    def __score_block(self, container: Tag, text: str) -> float:
        """Heuristic score: reward text density and penalise link-heavy noise."""
        if not text:
            return 0.0
        link_chars = sum(
            len(link.get_text(strip=True)) for link in container.find_all("a")
        )
        total_chars = max(1, len(text))
        text_density = 1.0 - min(1.0, link_chars / total_chars)
        length_bonus = min(1.0, len(text) / 4000.0)
        return text_density * 0.8 + length_bonus * 0.2

    def __clean_content(self, raw: str) -> str:
        if not raw:
            return ""
        raw = _WHITESPACE_RE.sub(" ", raw)
        lines = [line.strip() for line in raw.split("\n")]
        lines = [line for line in lines if line]
        return "\n".join(lines).strip()

    # ------------------------------------------------------------ image OCR
    def __extract_image_text(self, soup: BeautifulSoup, base_url: str) -> str:
        """Gather image alt text (always) and OCR image content (best-effort)."""
        fragments: list[str] = []
        for image in soup.find_all("img"):
            alt = image.get("alt", "").strip()
            src = image.get("src") or image.get("data-src")
            if alt:
                fragments.append(f"(Gambar - alt: {alt})")
            if self.__ocr_images and src:
                absolute = urljoin(base_url, src)
                if urlparse(absolute).netloc and absolute.lower().endswith(
                    (".png", ".jpg", ".jpeg", ".bmp", ".webp")
                ) and not _is_blocked_url(absolute):
                    ocr_text = self.__fetch_and_ocr(absolute)
                    if ocr_text:
                        fragments.append(f"(Gambar - OCR: {ocr_text})")
        return "\n".join(fragments)

    def __fetch_and_ocr(self, image_url: str) -> str:
        try:
            image_response = self.__session.get(
                image_url, timeout=min(self.__timeout_seconds, 10.0)
            )
            image_response.raise_for_status()
            if len(image_response.content) > _MAX_IMAGE_BYTES:
                return ""
            return ocr_image_bytes(image_response.content)
        except Exception as exc:  # noqa: BLE001 - best-effort image OCR
            logger.debug("Skipped OCR for '%s': %s", image_url, exc)
            return ""

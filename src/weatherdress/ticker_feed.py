"""Titres d'un flux RSS ou Atom, hors de la boucle d'affichage.

L'adresse vient de la config. Le bandeau ne lit qu'une phrase déjà en mémoire.
Un échec conserve la phrase précédente. L'adresse n'est pas écrite dans les journaux.
"""

from __future__ import annotations

import html
import re
import threading
import xml.etree.ElementTree as ElementTree

import requests

from . import ticker

MAX_ITEMS = 12
REQUEST_TIMEOUT_SECONDS = 15
_TAG = re.compile(r"<[^>]+>")
# Un agent « WeatherDress » reçoit souvent une page HTML à la place du RSS.
_FEED_USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/131.0.0.0 Safari/537.36"
)
# Radio-Canada sert parfois une page d'erreur si l'en-tête accepte trop de types.
_FEED_HEADERS = {
    "User-Agent": _FEED_USER_AGENT,
    "Accept": "application/rss+xml, application/atom+xml;q=0.9, application/xml;q=0.8, text/xml;q=0.7",
}
_FEED_HEADERS_STRICT = {
    "User-Agent": _FEED_USER_AGENT,
    "Accept": "application/rss+xml, application/atom+xml",
}


def normalize_feed_url(raw) -> str | None:
    """http et https seulement. Tout autre schéma, ou une adresse vide, est refusé."""
    if not isinstance(raw, str):
        return None
    url = raw.strip()
    if not url:
        return None
    lowered = url.lower()
    if lowered.startswith("https://") or lowered.startswith("http://"):
        return url
    return None


def feed_settings(config) -> dict | None:
    """Réglages utiles, ou None si aucun flux ne doit être lu."""
    spec = ticker.settings(config)
    if spec is None:
        return None
    url = normalize_feed_url(spec["url"])
    if url is None:
        return None
    return {"url": url, "refresh_seconds": spec["refresh_minutes"] * 60}


def parse_feed(payload) -> str:
    """Titres d'un RSS ou d'un Atom, joints pour le bandeau. Chaîne vide si illisible."""
    if isinstance(payload, str):
        payload = payload.encode("utf-8")
    if not payload:
        return ""
    try:
        root = ElementTree.fromstring(payload)
    except ElementTree.ParseError:
        return ""
    titles = []
    for element in root.iter():
        if _local(element.tag) not in ("item", "entry"):
            continue
        title = _title_of(element)
        if title:
            titles.append(title)
        if len(titles) >= MAX_ITEMS:
            break
    if not titles:
        return ""
    return "●  " + "  ●  ".join(titles) + "  ●  "


def phrase_for_render(fetcher, config) -> str:
    """Phrase du flux si elle est déjà là.

    Sans adresse, la phrase fixe. Avec une adresse, rien tant que le flux
    n'a pas fourni de titres : la phrase d'essai ne masque pas un échec.
    Vide si le bandeau est coupé.
    """
    spec = ticker.settings(config)
    if spec is None:
        return ""
    if fetcher is not None:
        live = fetcher.snapshot()
        if live:
            return live
    if spec["url"]:
        return ""
    return spec["text"]


def start_in_background(config, **kwargs):
    """Démarre le thread si une adresse valide est configurée. None sinon."""
    settings = feed_settings(config)
    if settings is None:
        spec = ticker.settings(config)
        if spec is not None and spec["url"] and normalize_feed_url(spec["url"]) is None:
            print("[ticker] Adresse du flux refusée : seul http et https sont acceptés.")
        return None
    fetcher = TickerFetcher(
        settings["url"],
        refresh_seconds=settings["refresh_seconds"],
        **kwargs,
    )
    fetcher.start()
    return fetcher


class TickerFetcher:
    """Télécharge un flux et publie une phrase. `refresh` est synchrone."""

    def __init__(self, url: str, *, refresh_seconds: int = 900, session=None):
        self.url = url
        self.refresh_seconds = max(1, int(refresh_seconds))
        self._session = session if session is not None else requests
        self._lock = threading.Lock()
        self._phrase = ""
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None

    def snapshot(self) -> str:
        with self._lock:
            return self._phrase

    def start(self) -> threading.Thread:
        if self._thread is not None:
            return self._thread
        self._thread = threading.Thread(target=self._loop, name="ticker-feed", daemon=True)
        self._thread.start()
        return self._thread

    def close(self) -> None:
        self._stop.set()
        if self._thread is not None:
            self._thread.join(timeout=1)

    def refresh(self) -> None:
        """Une tentative. Une erreur réseau ou un flux vide conserve la phrase précédente."""
        try:
            response, body, phrase = self._read(_FEED_HEADERS)
            if not phrase and not _body_is_xml(body):
                response, body, phrase = self._read(_FEED_HEADERS_STRICT)
        except Exception as exc:
            print(f"[ticker] Lecture du flux impossible ({type(exc).__name__}).")
            return
        if not phrase:
            status = getattr(response, "status_code", 200)
            status_n = int(status or 0)
            kind = "aucun titre" if _body_is_xml(body) else "corps illisible"
            print(
                f"[ticker] Flux refusé : {kind} "
                f"(HTTP {status_n}, {_response_type(response)})."
            )
            return
        with self._lock:
            self._phrase = phrase

    def _read(self, headers: dict) -> tuple:
        response = self._session.get(
            self.url,
            headers=headers,
            timeout=REQUEST_TIMEOUT_SECONDS,
        )
        status = getattr(response, "status_code", 200)
        if status and int(status) >= 400:
            raise OSError(f"statut {int(status)}")
        body = getattr(response, "content", b"") or b""
        return response, body, parse_feed(body)

    def _loop(self) -> None:
        while not self._stop.is_set():
            self.refresh()
            if self._stop.wait(self.refresh_seconds):
                break


def _response_type(response) -> str:
    headers = getattr(response, "headers", None) or {}
    getter = getattr(headers, "get", None)
    raw = getter("content-type") if getter else ""
    if not raw and getter:
        raw = getter("Content-Type")
    text = str(raw or "").split(";", 1)[0].strip()
    return text or "inconnu"


def _body_is_xml(payload) -> bool:
    if isinstance(payload, str):
        payload = payload.encode("utf-8")
    if not payload:
        return False
    try:
        ElementTree.fromstring(payload)
    except ElementTree.ParseError:
        return False
    return True


def _local(tag) -> str:
    if not isinstance(tag, str):
        return ""
    if "}" in tag:
        return tag.rsplit("}", 1)[-1]
    return tag


def _title_of(element) -> str:
    for child in list(element):
        if _local(child.tag) != "title":
            continue
        raw = "".join(child.itertext())
        text = _TAG.sub("", html.unescape(raw))
        return " ".join(text.split())
    return ""

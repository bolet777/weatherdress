"""Lecture d'un calendrier iCloud publié, hors de la boucle d'affichage.

L'adresse est un secret : elle n'est jamais écrite dans les journaux.
Le rendu lit seulement l'instantané déjà en mémoire.
Un cache valide est publié avant le premier appel réseau. La fenêtre de
quatre jours est recalculée dès le changement de date, sur le dernier ICS
déjà en mémoire, sans attendre le réseau.
"""

from __future__ import annotations

import hashlib
import json
import os
import threading
import time
from dataclasses import dataclass
from datetime import datetime, time as clock_time, timedelta
from pathlib import Path

import requests

from .paths import CALENDAR_CACHE_PATH, CALENDAR_META_PATH

HORIZON_DAYS = 4
REQUEST_TIMEOUT_SECONDS = 20


@dataclass(frozen=True)
class CalendarOccurrence:
    """Un passage dans la fenêtre de quatre jours, en heure locale d'affichage."""

    start: datetime
    end: datetime
    title: str
    all_day: bool


def normalize_calendar_url(raw) -> str | None:
    """`webcal://` devient `https://`. Tout autre schéma est refusé."""
    if not isinstance(raw, str):
        return None
    url = raw.strip()
    if not url:
        return None
    if url.lower().startswith("webcal://"):
        url = "https://" + url[9:]
    if not url.lower().startswith("https://"):
        return None
    return url


def calendar_settings(config) -> dict | None:
    """Réglages utiles, ou None si l'agenda ne doit pas tourner."""
    block = config.get("calendar") if isinstance(config, dict) else None
    if not isinstance(block, dict) or block.get("enabled") is not True:
        return None
    url = normalize_calendar_url(block.get("url"))
    if url is None:
        return None
    try:
        minutes = int(block.get("refresh_minutes", 30))
    except (TypeError, ValueError):
        minutes = 30
    return {"url": url, "refresh_seconds": max(1, minutes) * 60}


def url_fingerprint(url: str) -> str:
    return hashlib.sha256(url.encode("utf-8")).hexdigest()


def window_for(now: datetime, tz) -> tuple[datetime, datetime]:
    """De aujourd'hui 00:00 inclus à dans quatre jours 00:00 exclus."""
    local = now.astimezone(tz) if now.tzinfo is not None else now.replace(tzinfo=tz)
    start = local.replace(hour=0, minute=0, second=0, microsecond=0)
    return start, start + timedelta(days=HORIZON_DAYS)


def occurrences(ics, *, window_start: datetime, window_end: datetime, tz) -> list[CalendarOccurrence]:
    """Développe le calendrier sur la fenêtre. Lève si le texte est illisible."""
    import icalendar
    from recurring_ical_events import of

    text = ics.decode("utf-8", errors="replace") if isinstance(ics, bytes) else ics
    calendar = icalendar.Calendar.from_ical(text)
    found = []
    for event in of(calendar).between(window_start, window_end):
        status = event.get("STATUS")
        if status is not None and str(status).strip().upper() == "CANCELLED":
            continue
        parsed = _event_range(event, tz)
        if parsed is None:
            continue
        start, end, all_day = parsed
        if end <= window_start or start >= window_end:
            continue
        raw_title = event.get("SUMMARY")
        title = "" if raw_title is None else " ".join(str(raw_title).split())
        found.append(CalendarOccurrence(start, end, title, all_day))
    found.sort(key=lambda item: (item.start, item.title))
    return found


def _event_range(event, tz):
    stamp = event.get("DTSTART")
    if stamp is None:
        return None
    start_raw = stamp.dt
    end_prop = event.get("DTEND")
    end_raw = None if end_prop is None else end_prop.dt
    if isinstance(start_raw, datetime):
        start = _in_zone(start_raw, tz)
        if isinstance(end_raw, datetime):
            end = _in_zone(end_raw, tz)
        elif end_raw is not None and not isinstance(end_raw, datetime):
            end = datetime.combine(end_raw, clock_time.min, tzinfo=tz)
        else:
            end = start
        if end < start:
            return None
        return start, end, False
    start = datetime.combine(start_raw, clock_time.min, tzinfo=tz)
    if isinstance(end_raw, datetime):
        end = _in_zone(end_raw, tz)
    elif end_raw is not None:
        end = datetime.combine(end_raw, clock_time.min, tzinfo=tz)
    else:
        end = start + timedelta(days=1)
    if end < start:
        return None
    return start, end, True


def _in_zone(value: datetime, tz) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=tz)
    return value.astimezone(tz)


class CalendarFetcher:
    """Télécharge, met en cache, et publie un instantané. `refresh` est synchrone."""

    def __init__(
        self,
        url: str,
        *,
        refresh_seconds: int = 1800,
        tz=None,
        cache_path: Path | None = None,
        meta_path: Path | None = None,
        session=None,
        now=None,
    ):
        self.url = url
        self.refresh_seconds = max(1, int(refresh_seconds))
        self.tz = tz if tz is not None else datetime.now().astimezone().tzinfo
        self.cache_path = Path(cache_path or CALENDAR_CACHE_PATH)
        self.meta_path = Path(meta_path or CALENDAR_META_PATH)
        self._session = session if session is not None else requests
        self._now = now or (lambda: datetime.now(self.tz))
        self._lock = threading.Lock()
        self._events: tuple[CalendarOccurrence, ...] = ()
        self._ics: bytes | None = None
        self._window_date = None
        self._expand_error = None
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None

    def snapshot(self) -> tuple[CalendarOccurrence, ...]:
        with self._lock:
            return self._events

    def start(self) -> threading.Thread:
        if self._thread is not None:
            return self._thread
        # Le cache est prêt avant que le thread n'ouvre le réseau.
        self._publish_from_cache()
        self._thread = threading.Thread(
            target=self._loop, name="calendar-feed", daemon=True
        )
        self._thread.start()
        return self._thread

    def _loop(self) -> None:
        next_network = time.monotonic()
        while not self._stop.is_set():
            self._reexpand_if_needed()
            if time.monotonic() >= next_network:
                self.refresh()
                next_network = time.monotonic() + self.refresh_seconds
            timeout = self._wait_timeout(next_network)
            if timeout > 0 and self._stop.wait(timeout):
                break

    def refresh(self) -> None:
        """Une tentative. Une erreur réseau ou de lecture conserve le dernier état."""
        try:
            response = self._session.get(
                self.url,
                headers=self._headers(),
                timeout=REQUEST_TIMEOUT_SECONDS,
            )
        except Exception as exc:
            print(f"[calendar] Réseau indisponible ({type(exc).__name__}).")
            self._publish_from_cache()
            return
        final_url = getattr(response, "url", "") or ""
        if not str(final_url).lower().startswith("https://"):
            print("[calendar] Réponse hors HTTPS.")
            self._publish_from_cache()
            return
        status = getattr(response, "status_code", 0)
        if status == 304:
            self._publish_from_cache()
            return
        if status != 200:
            print(f"[calendar] Réponse HTTP {status}.")
            self._publish_from_cache()
            return
        body = getattr(response, "content", b"") or b""
        etag = _header(response, "ETag")
        if not self._publish_body(body):
            return
        self._write_cache(body, etag)

    def _headers(self) -> dict:
        headers = {
            "Accept": "text/calendar",
            "User-Agent": "WeatherDress",
        }
        etag = self._stored_etag()
        if etag:
            headers["If-None-Match"] = etag
        return headers

    def _publish_body(self, body: bytes) -> bool:
        if self._expand_and_store(body):
            return True
        print(f"[calendar] Calendrier illisible ({self._expand_error}).")
        self._publish_from_cache()
        return False

    def _publish_from_cache(self) -> None:
        body = self._read_cache_body()
        if body is None:
            return
        if self._expand_and_store(body):
            return
        print(f"[calendar] Copie locale illisible ({self._expand_error}).")

    def _expand_and_store(self, body: bytes) -> bool:
        """Découpe l'ICS sur la fenêtre courante. Ne vide pas l'écran en cas d'échec."""
        try:
            start, end = window_for(self._now(), self.tz)
            events = occurrences(body, window_start=start, window_end=end, tz=self.tz)
        except Exception as exc:
            self._expand_error = type(exc).__name__
            return False
        self._ics = bytes(body)
        self._window_date = start.date()
        self._set(events)
        return True

    def _needs_reexpand(self) -> bool:
        if not self._ics or self._window_date is None:
            return False
        start, _end = window_for(self._now(), self.tz)
        return self._window_date != start.date()

    def _reexpand_if_needed(self) -> None:
        """Nouveau jour local : même ICS, nouvelle fenêtre, aucun appel réseau."""
        if not self._needs_reexpand():
            return
        if self._expand_and_store(self._ics):
            return
        print(f"[calendar] Fenêtre non recalculée ({self._expand_error}).")
        start, _end = window_for(self._now(), self.tz)
        self._window_date = start.date()

    def _seconds_until_midnight(self) -> float:
        now = self._now()
        local = now.astimezone(self.tz) if now.tzinfo is not None else now.replace(tzinfo=self.tz)
        nxt = (local + timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
        return max(0.0, (nxt - local).total_seconds())

    def _wait_timeout(self, next_network: float) -> float:
        until_network = max(0.0, next_network - time.monotonic())
        return min(until_network, self._seconds_until_midnight())

    def _set(self, events) -> None:
        with self._lock:
            self._events = tuple(events)

    def _stored_etag(self) -> str | None:
        meta = self._read_meta()
        if meta is None:
            return None
        etag = meta.get("etag")
        return etag if isinstance(etag, str) and etag else None

    def _read_cache_body(self) -> bytes | None:
        meta = self._read_meta()
        if meta is None or meta.get("url_sha256") != url_fingerprint(self.url):
            return None
        try:
            return self.cache_path.read_bytes()
        except OSError:
            return None

    def _read_meta(self) -> dict | None:
        try:
            data = json.loads(self.meta_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError, UnicodeError):
            return None
        return data if isinstance(data, dict) else None

    def _write_cache(self, body: bytes, etag) -> None:
        meta = {
            "etag": etag if isinstance(etag, str) and etag else None,
            "url_sha256": url_fingerprint(self.url),
        }
        try:
            _write_private(self.cache_path, body)
            _write_private(
                self.meta_path,
                (json.dumps(meta, ensure_ascii=False) + "\n").encode("utf-8"),
            )
        except OSError as exc:
            print(f"[calendar] Cache non enregistré ({type(exc).__name__}).")


def _header(response, name: str):
    headers = getattr(response, "headers", {}) or {}
    getter = getattr(headers, "get", None)
    if getter is None:
        return None
    return getter(name)


def _write_private(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".tmp")
    try:
        descriptor = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
        os.chmod(temporary, 0o600)
        os.replace(temporary, path)
        os.chmod(path, 0o600)
    except Exception:
        if temporary.exists():
            temporary.unlink()
        raise


def events_for_render(fetcher):
    """Instantané déjà en mémoire. None si l'agenda est inactif. N'appelle pas le réseau."""
    if fetcher is None:
        return None
    return fetcher.snapshot()


def start_in_background(config, **kwargs):
    """Démarre le thread si l'agenda est actif. None sinon. Ne touche pas à l'écran."""
    block = config.get("calendar") if isinstance(config, dict) else None
    settings = calendar_settings(config)
    if settings is None:
        if isinstance(block, dict) and block.get("enabled") is True:
            print("[calendar] Adresse absente ou refusée : agenda inactif.")
        return None
    fetcher = CalendarFetcher(
        settings["url"],
        refresh_seconds=settings["refresh_seconds"],
        **kwargs,
    )
    fetcher.start()
    return fetcher

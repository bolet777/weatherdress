"""Lecture d'agenda : ICS fictif, cache, erreurs. Aucun appel iCloud."""

import json
import threading
import time
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest

from weatherdress import calendar_panel
from weatherdress.calendar_feed import (
    CalendarFetcher,
    calendar_settings,
    events_for_render,
    normalize_calendar_url,
    occurrences,
    start_in_background,
    window_for,
)

pytest.importorskip("icalendar")
pytest.importorskip("recurring_ical_events")

TZ = ZoneInfo("America/Toronto")
NOW = datetime(2026, 11, 4, 9, 30, tzinfo=TZ)
FIXTURE = Path(__file__).parent / "fixtures" / "calendar_window.ics"
TOKEN = "SECRET-CAL-TOKEN"
WEB_URL = f"webcal://cal.example.test/{TOKEN}"
HTTPS_URL = f"https://cal.example.test/{TOKEN}"


class Response:
    def __init__(self, status, content=b"", headers=None, url=HTTPS_URL):
        self.status_code = status
        self.content = content
        self.headers = headers or {}
        self.url = url


class Session:
    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = []

    def get(self, url, headers=None, timeout=None):
        self.calls.append({"url": url, "headers": headers or {}, "timeout": timeout})
        responder = self.responses.pop(0)
        if isinstance(responder, Exception):
            raise responder
        return responder


def _window():
    return window_for(NOW, TZ)


def _titles(events):
    return [event.title for event in events]


def test_webcal_becomes_https_and_other_schemes_are_refused():
    assert normalize_calendar_url(WEB_URL) == HTTPS_URL
    assert normalize_calendar_url(f"  {WEB_URL}  ") == HTTPS_URL
    assert normalize_calendar_url("http://cal.example.test/x") is None
    assert normalize_calendar_url("") is None
    assert normalize_calendar_url(None) is None


def test_disabled_calendar_does_not_start(capsys):
    session = Session([AssertionError("réseau")])
    assert calendar_settings({"calendar": {"enabled": False, "url": WEB_URL}}) is None
    assert start_in_background(
        {"calendar": {"enabled": False, "url": WEB_URL}},
        session=session,
        tz=TZ,
    ) is None
    assert session.calls == []
    assert TOKEN not in capsys.readouterr().out
    assert start_in_background({"calendar": {"enabled": True, "url": "http://x"}}) is None
    assert TOKEN not in capsys.readouterr().out


def test_fixture_keeps_four_day_window_only():
    start, end = _window()
    events = occurrences(FIXTURE.read_bytes(), window_start=start, window_end=end, tz=TZ)
    assert _titles(events) == [
        "Chevauche la nuit",
        "Piano déplacé",
        "Dentiste",
        "Vacances",
        "Appel",
        "Heure flottante",
    ]
    piano = events[1]
    assert piano.start.astimezone(TZ).hour == 11
    assert piano.start.astimezone(TZ).minute == 30
    vacation = events[3]
    assert vacation.all_day is True
    assert vacation.start.date().isoformat() == "2026-11-05"
    assert vacation.end.date().isoformat() == "2026-11-07"
    call = events[4]
    assert call.start.astimezone(TZ).hour == 5
    floating = events[5]
    assert floating.start.hour == 14
    assert floating.start.tzinfo == TZ
    assert "Rendez-vous annulé" not in _titles(events)
    assert "Hors fenêtre" not in _titles(events)
    assert "Piano" not in _titles(events)


def test_network_error_keeps_cache_and_hides_the_url(tmp_path, capsys):
    body = FIXTURE.read_bytes()
    session = Session(
        [
            Response(200, body, {"ETag": '"v1"'}),
            OSError(f"connexion coupée {TOKEN}"),
        ]
    )
    feed = CalendarFetcher(
        HTTPS_URL,
        tz=TZ,
        cache_path=tmp_path / "calendar.ics",
        meta_path=tmp_path / "calendar.meta.json",
        session=session,
        now=lambda: NOW,
    )
    feed.refresh()
    assert _titles(feed.snapshot())[1] == "Piano déplacé"
    feed._set(())
    feed.refresh()
    assert _titles(feed.snapshot())[1] == "Piano déplacé"
    logged = capsys.readouterr().out
    assert TOKEN not in logged
    assert "OSError" in logged
    assert session.calls[0]["url"] == HTTPS_URL
    assert session.calls[1]["headers"]["If-None-Match"] == '"v1"'
    meta = json.loads((tmp_path / "calendar.meta.json").read_text(encoding="utf-8"))
    assert "url" not in meta
    assert TOKEN not in json.dumps(meta)


def test_not_modified_rereads_the_local_copy(tmp_path):
    body = FIXTURE.read_bytes()
    session = Session(
        [
            Response(200, body, {"ETag": '"v1"'}),
            Response(304, b"", {"ETag": '"v1"'}),
        ]
    )
    feed = CalendarFetcher(
        HTTPS_URL,
        tz=TZ,
        cache_path=tmp_path / "calendar.ics",
        meta_path=tmp_path / "calendar.meta.json",
        session=session,
        now=lambda: NOW,
    )
    feed.refresh()
    feed._set(())
    feed.refresh()
    assert len(feed.snapshot()) == 6


def test_foreign_cache_is_ignored(tmp_path, capsys):
    cache = tmp_path / "calendar.ics"
    meta = tmp_path / "calendar.meta.json"
    cache.write_bytes(FIXTURE.read_bytes())
    meta.write_text(
        json.dumps({"etag": '"autre"', "url_sha256": "pas-le-bon"}) + "\n",
        encoding="utf-8",
    )
    session = Session([OSError("down")])
    feed = CalendarFetcher(
        HTTPS_URL,
        tz=TZ,
        cache_path=cache,
        meta_path=meta,
        session=session,
        now=lambda: NOW,
    )
    feed.refresh()
    assert feed.snapshot() == ()
    assert TOKEN not in capsys.readouterr().out


def test_refresh_runs_outside_the_caller(tmp_path):
    started = threading.Event()
    release = threading.Event()

    class Slow:
        def get(self, url, headers=None, timeout=None):
            started.set()
            assert release.wait(2)
            return Response(200, FIXTURE.read_bytes(), url=url)

    feed = CalendarFetcher(
        HTTPS_URL,
        refresh_seconds=3600,
        tz=TZ,
        cache_path=tmp_path / "calendar.ics",
        meta_path=tmp_path / "calendar.meta.json",
        session=Slow(),
        now=lambda: NOW,
    )
    feed.start()
    assert started.wait(1)
    assert feed.snapshot() == ()
    release.set()
    deadline = time.monotonic() + 3
    while time.monotonic() < deadline and not feed.snapshot():
        time.sleep(0.05)
    assert len(feed.snapshot()) == 6
    feed._stop.set()


def _ics_with(**events):
    """Ajoute des événements au calendrier fictif. `events` : titre → (début, fin) compactés."""
    blocks = []
    for title, (start, end) in events.items():
        blocks.append(
            "BEGIN:VEVENT\n"
            f"UID:{title}@test\n"
            f"DTSTART;TZID=America/Toronto:{start}\n"
            f"DTEND;TZID=America/Toronto:{end}\n"
            f"SUMMARY:{title}\n"
            "END:VEVENT\n"
        )
    extra = "".join(blocks).encode()
    return FIXTURE.read_bytes().replace(b"END:VCALENDAR", extra + b"END:VCALENDAR\n")


def test_start_publishes_a_matching_cache_before_the_network(tmp_path):
    started = threading.Event()
    release = threading.Event()
    seen = {}

    class Slow:
        def get(self, url, headers=None, timeout=None):
            seen["headers"] = headers or {}
            started.set()
            assert release.wait(2)
            return Response(200, b"BEGIN:VCALENDAR\nEND:VCALENDAR\n", url=url)

    feed = CalendarFetcher(
        HTTPS_URL,
        refresh_seconds=3600,
        tz=TZ,
        cache_path=tmp_path / "calendar.ics",
        meta_path=tmp_path / "calendar.meta.json",
        session=Slow(),
        now=lambda: NOW,
    )
    feed._write_cache(FIXTURE.read_bytes(), '"v1"')
    feed.start()
    assert _titles(feed.snapshot())[1] == "Piano déplacé"
    assert started.wait(1)
    assert seen["headers"]["If-None-Match"] == '"v1"'
    assert TOKEN not in repr(seen)
    release.set()
    feed._stop.set()


def test_start_ignores_a_foreign_or_broken_cache(tmp_path, capsys):
    started = threading.Event()
    release = threading.Event()

    class Slow:
        def get(self, url, headers=None, timeout=None):
            started.set()
            assert release.wait(2)
            return Response(200, FIXTURE.read_bytes(), url=url)

    cache = tmp_path / "calendar.ics"
    meta = tmp_path / "calendar.meta.json"
    cache.write_bytes(FIXTURE.read_bytes())
    meta.write_text(
        json.dumps({"etag": '"autre"', "url_sha256": "pas-le-bon"}) + "\n",
        encoding="utf-8",
    )
    foreign = CalendarFetcher(
        HTTPS_URL,
        refresh_seconds=3600,
        tz=TZ,
        cache_path=cache,
        meta_path=meta,
        session=Slow(),
        now=lambda: NOW,
    )
    foreign.start()
    assert foreign.snapshot() == ()
    assert started.wait(1)
    release.set()
    foreign._stop.set()

    held = threading.Event()
    stay = threading.Event()

    class Hold:
        def get(self, url, headers=None, timeout=None):
            held.set()
            stay.wait(2)
            return Response(200, FIXTURE.read_bytes(), url=url)

    broken = CalendarFetcher(
        HTTPS_URL,
        refresh_seconds=3600,
        tz=TZ,
        cache_path=tmp_path / "broken.ics",
        meta_path=tmp_path / "broken.meta.json",
        session=Hold(),
        now=lambda: NOW,
    )
    broken._write_cache(b"ceci n'est pas un calendrier", '"v1"')
    broken.start()
    assert held.wait(1)
    assert broken.snapshot() == ()
    logged = capsys.readouterr().out
    assert "illisible" in logged
    assert TOKEN not in logged
    stay.set()
    broken._stop.set()


def test_midnight_reexpands_stored_ics_without_network(tmp_path):
    body = _ics_with(
        **{
            "Jour entrant": ("20261108T100000", "20261108T110000"),
            "Nuit en cours": ("20261104T220000", "20261105T030000"),
        }
    )
    clock = [datetime(2026, 11, 4, 23, 50, tzinfo=TZ)]
    session = Session([Response(200, body, {"ETag": '"v1"'})])
    feed = CalendarFetcher(
        HTTPS_URL,
        refresh_seconds=3600,
        tz=TZ,
        cache_path=tmp_path / "calendar.ics",
        meta_path=tmp_path / "calendar.meta.json",
        session=session,
        now=lambda: clock[0],
    )
    feed.refresh()
    (tmp_path / "calendar.ics").unlink()
    assert "Jour entrant" not in _titles(feed.snapshot())
    assert "Nuit en cours" in _titles(feed.snapshot())
    assert "Dentiste" in _titles(feed.snapshot())

    clock[0] = datetime(2026, 11, 5, 0, 10, tzinfo=TZ)
    feed._reexpand_if_needed()
    titles = _titles(feed.snapshot())
    assert "Jour entrant" in titles
    assert "Nuit en cours" in titles
    assert "Dentiste" not in titles
    assert "Chevauche la nuit" not in titles
    assert session.calls == [session.calls[0]]
    assert len(session.calls) == 1

    shown = [
        event.title
        for event in calendar_panel.events_on_day(feed.snapshot(), clock[0].date(), clock[0])
    ]
    assert "Nuit en cours" in shown
    assert "Dentiste" not in shown
    assert TOKEN not in json.dumps(
        json.loads((tmp_path / "calendar.meta.json").read_text(encoding="utf-8"))
    )


def test_midnight_wakes_the_thread_before_the_next_download(tmp_path):
    body = _ics_with(**{"Jour entrant": ("20261108T100000", "20261108T110000")})
    clock = [datetime(2026, 11, 4, 23, 59, 59, tzinfo=TZ)]
    calls = []
    waiting = threading.Event()

    class Net:
        def get(self, url, headers=None, timeout=None):
            calls.append(url)
            return Response(304, b"", url=url)

    feed = CalendarFetcher(
        HTTPS_URL,
        refresh_seconds=3600,
        tz=TZ,
        cache_path=tmp_path / "calendar.ics",
        meta_path=tmp_path / "calendar.meta.json",
        session=Net(),
        now=lambda: clock[0],
    )
    feed._write_cache(body, '"v1"')
    real_wait = feed._stop.wait

    def wait(seconds):
        waiting.set()
        return real_wait(seconds)

    feed._stop.wait = wait
    feed.start()
    assert "Jour entrant" not in _titles(feed.snapshot())
    assert waiting.wait(2)
    assert len(calls) == 1
    clock[0] = datetime(2026, 11, 5, 0, 10, tzinfo=TZ)
    deadline = time.monotonic() + 3
    while time.monotonic() < deadline and "Jour entrant" not in _titles(feed.snapshot()):
        time.sleep(0.02)
    assert "Jour entrant" in _titles(feed.snapshot())
    assert len(calls) == 1
    feed._stop.set()


def test_same_day_keeps_an_event_that_is_still_running():
    events = occurrences(
        FIXTURE.read_bytes(),
        window_start=_window()[0],
        window_end=_window()[1],
        tz=TZ,
    )
    noon = datetime(2026, 11, 4, 12, 0, tzinfo=TZ)
    shown = [event.title for event in calendar_panel.events_on_day(events, noon.date(), noon)]
    assert "Piano déplacé" in shown
    assert "Dentiste" in shown
    assert "Chevauche la nuit" not in shown


def test_events_for_render_reads_memory_only():
    class Trap:
        def snapshot(self):
            return ("déjà prêt",)

        def refresh(self):
            raise AssertionError("réseau")

    assert events_for_render(None) is None
    assert events_for_render(Trap()) == ("déjà prêt",)

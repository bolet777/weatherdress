"""Agenda à l'écran : rotation, fenêtre vide, débordement, décor immobile."""

import os
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

import pygame  # noqa: E402
import pytest  # noqa: E402

pytest.importorskip("pygame")

pygame.init()
pygame.display.set_mode((800, 480))

from weatherdress import calendar_panel  # noqa: E402
from weatherdress import display  # noqa: E402
from weatherdress.calendar_feed import CalendarOccurrence  # noqa: E402

TZ = ZoneInfo("America/Toronto")
NOW = datetime(2026, 11, 4, 9, 30, tzinfo=TZ)
WASH = calendar_panel.today_wash_on((255, 255, 255))

TRANSIT = {
    "gtfs_url": "https://example.test/gtfs.zip",
    "metro_station": "Outremont",
    "metro_route_id": "5",
    "bus_stops": {"1": "Snowdon"},
    "metro_directions": {"Station Snowdon": "Snowdon"},
}
DEPARTURES = {
    "bus": {"1": {"route": "51", "label": "Snowdon", "minutes": [4, 12]}},
    "metro": {"Station Snowdon": [3, 9]},
}


def _config(*, transit=True, calendar=True, rotate=15, mode="after_character"):
    data = {
        "screen_width": 800,
        "screen_height": 480,
        "use_weather_background": False,
        "use_ambient_weather_background": False,
        "background_color": [255, 255, 255],
        "circle_background_color": [230, 230, 230],
        "language": "fr",
        "units": "metric",
        "layout": {"weather_mode": mode},
    }
    if transit:
        data["transit"] = dict(TRANSIT)
    if calendar:
        data["calendar"] = {
            "enabled": True,
            "url": "",
            "refresh_minutes": 30,
            "rotate_seconds": rotate,
        }
    return data


def _outfit():
    return {
        "character": "normal_woman1",
        "current_accessories": [],
        "future_accessories": [],
    }


def _weather():
    return {
        "temp": 3.0,
        "description": "ciel dégagé",
        "condition_id": 800,
        "icon": "01d",
    }


def _at(hour, minute, title, *, day=0, hours=1, all_day=False):
    start = datetime(2026, 11, 4, hour, minute, tzinfo=TZ) + timedelta(days=day)
    if all_day:
        start = datetime(2026, 11, 4, tzinfo=TZ) + timedelta(days=day)
        end = start + timedelta(days=hours)
        return CalendarOccurrence(start, end, title, True)
    return CalendarOccurrence(start, start + timedelta(hours=hours), title, False)


def _busy():
    titles = ("Médiathèque", "Soccer", "Dîner", "Ortho", "Épicerie", "Film")
    events = [
        _at(7, 0, "Déjà fini"),
        _at(11, 15, "Cours de natation dont le titre est vraiment très long " * 3),
    ]
    for index, title in enumerate(titles):
        events.append(_at(10 + index, 5, title))
    events.append(_at(9, 0, "Dentiste", day=1))
    return events


def _paint(config, events, phase, monkeypatch):
    monkeypatch.setattr(pygame.display, "flip", lambda: None)
    screen = pygame.Surface((800, 480))
    metrics = {}
    display.render(
        screen,
        _outfit(),
        _weather(),
        os.getcwd(),
        config,
        transit_data=DEPARTURES if "transit" in config else None,
        transit_phase_t=0.0,
        calendar_events=events,
        calendar_phase_t=phase,
        shown_at=NOW,
        frame_metrics=metrics,
    )
    return screen, metrics


def _rgb(screen):
    return pygame.image.tostring(screen, "RGB")


def _above(screen, top):
    return pygame.image.tostring(screen.subsurface((0, 0, 800, top)), "RGB")


def _left(screen, column_left):
    width = max(1, int(column_left))
    return pygame.image.tostring(screen.subsurface((0, 0, width, 480)), "RGB")


def _count_exact(screen, rect, rgb):
    found = 0
    for y in range(rect.top, rect.bottom):
        for x in range(rect.left, rect.right):
            pixel = screen.get_at((x, y))
            if (pixel.r, pixel.g, pixel.b) == rgb:
                found += 1
    return found


def test_choose_side_rotation_and_fallbacks():
    assert calendar_panel.rotate_period({}) == 15
    assert calendar_panel.rotate_period({"calendar": {"rotate_seconds": "abc"}}) == 15
    assert calendar_panel.rotate_period({"calendar": {"rotate_seconds": -4}}) == 0
    common = dict(calendar_enabled=True, transit_enabled=True, has_events=True)
    assert calendar_panel.choose_side(**common, rotate_seconds=15, phase_t=0) == "transit"
    assert calendar_panel.choose_side(**common, rotate_seconds=15, phase_t=14.9) == "transit"
    assert calendar_panel.choose_side(**common, rotate_seconds=15, phase_t=15) == "calendar"
    assert calendar_panel.choose_side(**common, rotate_seconds=15, phase_t=30) == "transit"
    assert calendar_panel.choose_side(**common, rotate_seconds=0, phase_t=15) == "transit"
    assert (
        calendar_panel.choose_side(
            calendar_enabled=True,
            transit_enabled=False,
            has_events=True,
            rotate_seconds=0,
            phase_t=15,
        )
        == "calendar"
    )
    assert (
        calendar_panel.choose_side(
            calendar_enabled=True,
            transit_enabled=True,
            has_events=False,
            rotate_seconds=15,
            phase_t=15,
        )
        == "transit"
    )
    assert (
        calendar_panel.choose_side(
            calendar_enabled=False,
            transit_enabled=True,
            has_events=True,
            rotate_seconds=15,
            phase_t=15,
        )
        == "transit"
    )
    assert (
        calendar_panel.choose_side(
            calendar_enabled=False,
            transit_enabled=False,
            has_events=True,
            rotate_seconds=15,
            phase_t=15,
        )
        == "none"
    )


def test_disabled_calendar_matches_the_current_screen(monkeypatch):
    events = _busy()
    off, _metrics_off = _paint(_config(calendar=False), events, 15, monkeypatch)
    omitted, _metrics_omitted = _paint(_config(calendar=False), None, 15, monkeypatch)
    assert _rgb(off) == _rgb(omitted)


def test_empty_snapshot_keeps_transit_even_on_agenda_phase(monkeypatch):
    baseline, _base = _paint(_config(calendar=False), None, 15, monkeypatch)
    empty, metrics = _paint(_config(), (), 15, monkeypatch)
    assert metrics["side"] == "transit"
    assert _rgb(empty) == _rgb(baseline)
    assert _count_exact(empty, metrics["panel"], WASH) == 0


def test_rotation_is_a_hard_cut_inside_the_transit_rect(monkeypatch):
    events = (_at(11, 15, "Cours de natation"), _at(9, 0, "Dentiste", day=1))
    baseline, base = _paint(_config(calendar=False), None, 0, monkeypatch)
    transit, transit_metrics = _paint(_config(), events, 0, monkeypatch)
    agenda, agenda_metrics = _paint(_config(), events, 15, monkeypatch)
    assert transit_metrics["side"] == "transit"
    assert agenda_metrics["side"] == "calendar"
    assert transit_metrics["panel"] == agenda_metrics["panel"] == base["panel"]
    assert transit_metrics["weather_top"] == agenda_metrics["weather_top"] == base["weather_top"]
    top = agenda_metrics["transit_top"]
    assert top > 40
    assert _above(transit, top) == _above(agenda, top) == _above(baseline, top)
    assert _left(transit, transit_metrics["column_left"]) == _left(agenda, agenda_metrics["column_left"])
    assert _rgb(transit) == _rgb(baseline)
    assert _count_exact(transit, transit_metrics["panel"], WASH) == 0
    assert _count_exact(agenda, agenda_metrics["panel"], WASH) > 100
    laid = calendar_panel.layout_agenda(events, NOW, agenda_metrics["panel"])
    times = [piece.text for piece in laid.pieces if piece.role == "time" and piece.zone == "today"]
    assert times == ["11:15"]


def test_rotate_zero_keeps_transit_when_transit_is_available(monkeypatch):
    events = (_at(11, 15, "Piano"),)
    baseline, _base = _paint(_config(calendar=False), None, 40, monkeypatch)
    frozen, metrics = _paint(_config(rotate=0), events, 40, monkeypatch)
    assert metrics["side"] == "transit"
    assert _rgb(frozen) == _rgb(baseline)


def test_overflow_puts_plus_n_on_the_last_visible_line(monkeypatch):
    events = _busy()
    _screen, metrics = _paint(_config(), events, 15, monkeypatch)
    assert metrics["side"] == "calendar"
    laid = calendar_panel.layout_agenda(events, NOW, metrics["panel"])
    titles = [piece for piece in laid.pieces if piece.zone == "today" and piece.role == "title"]
    times = [piece for piece in laid.pieces if piece.zone == "today" and piece.role == "time"]
    more = [piece for piece in laid.pieces if piece.zone == "today" and piece.role == "more"]
    assert titles
    assert len(titles) < 6
    assert more[0].text == f"+{len([e for e in events if e.start.date() == NOW.date() and e.end > NOW]) - len(titles)}"
    assert "Déjà fini" not in [piece.text for piece in laid.pieces]
    assert more[0].rect.top == titles[-1].rect.top == times[-1].rect.top
    assert calendar_panel.ELLIPSIS not in times[-1].text
    assert titles[-1].rect.right <= more[0].rect.left
    assert all(metrics["panel"].contains(piece.rect) for piece in laid.pieces)


def test_no_events_and_no_transit_leaves_the_weather_where_it_is(monkeypatch):
    baseline, base = _paint(_config(transit=False, calendar=False), None, 15, monkeypatch)
    idle, metrics = _paint(_config(transit=False), (), 15, monkeypatch)
    assert metrics["side"] == "none"
    assert metrics["weather_top"] == base["weather_top"]
    assert _rgb(idle) == _rgb(baseline)


def test_calendar_alone_uses_the_space_under_the_weather(monkeypatch):
    events = (_at(11, 15, "Piano"), _at(14, 0, "Dentiste", day=1))
    baseline, base = _paint(_config(transit=False, calendar=False), None, 0, monkeypatch)
    alone, metrics = _paint(_config(transit=False, rotate=0), events, 0, monkeypatch)
    assert metrics["side"] == "calendar"
    assert metrics["transit_top"] is None
    assert metrics["weather_top"] == base["weather_top"]
    assert metrics["panel"].top >= metrics["weather_bottom"]
    assert metrics["panel"].height >= 48
    assert _above(alone, metrics["panel"].top) == _above(baseline, metrics["panel"].top)
    assert _left(alone, metrics["column_left"]) == _left(baseline, metrics["column_left"])
    assert _count_exact(alone, metrics["panel"], WASH) > 50
    assert _count_exact(baseline, metrics["panel"], WASH) == 0


def test_compact_agenda_keeps_the_transit_rectangle(monkeypatch):
    one = (_at(11, 15, "Piano"),)
    many = _busy()
    quiet, quiet_metrics = _paint(_config(), one, 15, monkeypatch)
    busy, busy_metrics = _paint(_config(), many, 15, monkeypatch)
    assert quiet_metrics["panel"] == busy_metrics["panel"]
    assert quiet_metrics["weather_top"] == busy_metrics["weather_top"]
    top = quiet_metrics["transit_top"]
    assert _above(quiet, top) == _above(busy, top)
    assert quiet_metrics["side"] == busy_metrics["side"] == "calendar"


def test_screen_right_stays_free_of_the_agenda(monkeypatch):
    events = (_at(11, 15, "Piano"),)
    screen, metrics = _paint(
        _config(transit=False, mode="screen_right"),
        events,
        15,
        monkeypatch,
    )
    assert metrics["side"] == "none"
    assert _count_exact(screen, pygame.Rect(0, 0, 800, 480), WASH) == 0

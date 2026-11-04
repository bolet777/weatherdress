"""Maquette agenda : tri, ellipse, +N, et décor immobile."""

import importlib.util
import os
from datetime import datetime, timedelta
from pathlib import Path

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

import pygame  # noqa: E402
import pytest  # noqa: E402

pytest.importorskip("pygame")

pygame.init()
pygame.display.set_mode((800, 480))

_SPEC = importlib.util.spec_from_file_location(
    "calendar_mockup",
    Path(__file__).resolve().parents[1] / "scripts" / "calendar_mockup.py",
)
mockup = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(mockup)

from weatherdress.config_file import load_config  # noqa: E402

NOW = datetime(2026, 11, 4, 9, 30)
PANEL = pygame.Rect(20, 40, 380, 220)


def _ended_and_six():
    today = NOW.date()
    events = [
        mockup.Event(
            datetime(2026, 11, 4, 7, 0),
            datetime(2026, 11, 4, 8, 0),
            "Déjà fini",
        )
    ]
    hours = (10, 11, 13, 15, 17, 20)
    titles = ("Médiathèque", "Soccer", "Dîner", "Ortho", "Épicerie", "Film")
    for hour, title in zip(hours, titles):
        start = datetime.combine(today, datetime.min.time()).replace(hour=hour)
        events.append(mockup.Event(start, start + timedelta(hours=1), title))
    return events


def test_empty_window_hides_agenda():
    assert mockup.should_show_agenda([], NOW) is False
    laid = mockup.layout_agenda([], NOW, PANEL)
    assert laid.show is False
    assert laid.pieces == []


def test_event_in_three_days_shows_today_dash():
    day = NOW.date() + timedelta(days=3)
    start = datetime.combine(day, datetime.min.time()).replace(hour=15)
    events = [mockup.Event(start, start + timedelta(hours=1), "Anniversaire")]
    assert mockup.should_show_agenda(events, NOW) is True
    laid = mockup.layout_agenda(events, NOW, PANEL)
    today_dash = [
        piece.text
        for piece in laid.pieces
        if piece.zone == "today" and piece.role == "dash"
    ]
    assert today_dash == ["—"]
    upcoming = [
        piece.text
        for piece in laid.pieces
        if piece.day_offset == 3 and piece.role == "title"
    ]
    assert upcoming == ["Anniversaire"]


def test_nearest_events_and_plus_n_skip_finished():
    laid = mockup.layout_agenda(_ended_and_six(), NOW, PANEL)
    titles = [piece for piece in laid.pieces if piece.zone == "today" and piece.role == "title"]
    more = [piece for piece in laid.pieces if piece.zone == "today" and piece.role == "more"]
    order = ["Médiathèque", "Soccer", "Dîner", "Ortho", "Épicerie", "Film"]
    assert titles
    assert [piece.text for piece in titles] == order[: len(titles)]
    assert len(more) == 1
    assert more[0].text == f"+{6 - len(titles)}"
    assert more[0].rect.top == titles[-1].rect.top
    assert titles[-1].rect.right <= more[0].rect.left
    last_time = [
        piece for piece in laid.pieces if piece.zone == "today" and piece.role == "time"
    ][-1]
    assert last_time.rect.top == titles[-1].rect.top
    assert mockup.ELLIPSIS not in last_time.text
    assert "Déjà fini" not in [piece.text for piece in laid.pieces]
    assert len(titles) < 6


def test_long_title_keeps_full_time_inside_panel():
    start = datetime(2026, 11, 4, 11, 15)
    title = "Mottrèslong " * 8
    events = [mockup.Event(start, start + timedelta(hours=1), title)]
    font = pygame.font.SysFont("sans-serif", 28, bold=True)
    assert font.size(title)[0] > PANEL.width
    laid = mockup.layout_agenda(events, NOW, PANEL)
    times = [piece for piece in laid.pieces if piece.zone == "today" and piece.role == "time"]
    titles = [piece for piece in laid.pieces if piece.zone == "today" and piece.role == "title"]
    assert len(times) == 1
    assert times[0].text == "11:15"
    assert mockup.ELLIPSIS not in times[0].text
    assert titles and titles[0].text.endswith(mockup.ELLIPSIS)
    assert times[0].rect.right + mockup.TIME_GAP <= titles[0].rect.left
    for piece in laid.pieces:
        assert piece.rect.left >= laid.panel.left
        assert piece.rect.right <= laid.panel.right
        assert piece.rect.top >= laid.panel.top
        assert piece.rect.bottom <= laid.panel.bottom


def test_upcoming_time_stays_full_when_title_and_plus_n():
    tomorrow = NOW.date() + timedelta(days=1)
    events = []
    for hour, extra in ((9, 0), (14, 1), (18, 2)):
        start = datetime.combine(tomorrow, datetime.min.time()).replace(hour=hour)
        events.append(
            mockup.Event(start, start + timedelta(hours=1), "Titre beaucoup trop long " * 4)
        )
    laid = mockup.layout_agenda(events, NOW, PANEL)
    times = [
        piece
        for piece in laid.pieces
        if piece.day_offset == 1 and piece.role == "time"
    ]
    titles = [
        piece
        for piece in laid.pieces
        if piece.day_offset == 1 and piece.role == "title"
    ]
    more = [
        piece
        for piece in laid.pieces
        if piece.day_offset == 1 and piece.role == "more"
    ]
    assert times[0].text == "09:00"
    assert mockup.ELLIPSIS not in times[0].text
    assert more[0].text == "+2"
    assert titles[0].text.endswith(mockup.ELLIPSIS)
    assert times[0].rect.right <= titles[0].rect.left
    assert titles[0].rect.right <= more[0].rect.left
    for piece in laid.pieces:
        assert laid.panel.contains(piece.rect)


def test_event_titles_are_not_bold_and_times_stay_orange():
    start = datetime(2026, 11, 4, 11, 15)
    events = [mockup.Event(start, start + timedelta(hours=1), "Cours de natation")]
    laid = mockup.layout_agenda(events, NOW, PANEL)
    _style, fonts, _slots = mockup._pick_style(PANEL.height)
    _header, time_font, title_font, _next = fonts
    title = next(piece for piece in laid.pieces if piece.role == "title")
    clock = next(piece for piece in laid.pieces if piece.zone == "today" and piece.role == "time")
    assert title.rect.width == title_font.size(title.text)[0]
    assert clock.rect.width == time_font.size(clock.text)[0]
    assert not title_font.get_bold()
    assert time_font.get_bold()
    assert clock.color == mockup.TODAY_TIME
    assert clock.text == "11:15"


def test_blue_section_follows_today_event_count():
    today = NOW.date()
    one = [
        mockup.Event(
            datetime(2026, 11, 4, 11, 0),
            datetime(2026, 11, 4, 12, 0),
            "Piano",
        )
    ]
    many = []
    for hour in (10, 11, 13, 15, 17, 20):
        start = datetime.combine(today, datetime.min.time()).replace(hour=hour)
        many.append(mockup.Event(start, start + timedelta(hours=1), f"Cours {hour}"))
    short = mockup.layout_agenda(one, NOW, PANEL)
    full = mockup.layout_agenda(many, NOW, PANEL)
    assert short.panel.size == full.panel.size == (PANEL.w, PANEL.h)
    assert short.divider_y < full.divider_y
    upcoming_top = min(piece.rect.top for piece in full.pieces if piece.zone == "upcoming")
    assert full.divider_y < upcoming_top
    assert short.divider_y < upcoming_top


def test_fit_ellipsis_keeps_short_text():
    font = pygame.font.SysFont("sans-serif", 20, bold=False)
    assert mockup.fit_ellipsis(font, "Piano", 400) == "Piano"
    squeezed = mockup.fit_ellipsis(font, "A" * 80, 40)
    assert squeezed.endswith(mockup.ELLIPSIS)
    assert font.size(squeezed)[0] <= 40


def test_chrome_stays_put_between_agenda_and_transit():
    config = load_config()
    busy = mockup.events_for_scenario("journee-chargee", NOW)
    screen_a = pygame.Surface((800, 480))
    screen_b = pygame.Surface((800, 480))
    frame_a = mockup.paint_frame(screen_a, config, busy, NOW)
    frame_b = mockup.paint_frame(screen_b, config, [], NOW)
    assert frame_a.show_agenda is True
    assert frame_b.show_agenda is False
    assert frame_a.weather_top == frame_b.weather_top
    assert frame_a.transit_top == frame_b.transit_top
    assert frame_a.panel == frame_b.panel
    top = frame_a.transit_top
    assert top and top > 40
    above_a = pygame.image.tostring(
        screen_a.subsurface((0, 0, 800, top)), "RGB"
    )
    above_b = pygame.image.tostring(
        screen_b.subsurface((0, 0, 800, top)), "RGB"
    )
    assert above_a == above_b

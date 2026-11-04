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


def _all_day(day, title):
    start = datetime.combine(day, datetime.min.time())
    return mockup.Event(start, start + timedelta(days=1), title, all_day=True)


def test_long_all_day_title_drops_journee_and_keeps_the_place():
    day = NOW.date() + timedelta(days=3)
    title = "Centre des Sciences - Ubi"
    laid = mockup.layout_agenda([_all_day(day, title)], NOW, PANEL)
    row = [piece for piece in laid.pieces if piece.day_offset == 3]
    assert [piece.text for piece in row if piece.role == "time"] == []
    shown = next(piece.text for piece in row if piece.role == "title")
    assert shown.startswith("Centre des Sciences")
    assert len(shown) > len("Centre des Scien")
    assert all(laid.panel.contains(piece.rect) for piece in laid.pieces)
    day_piece = next(piece for piece in row if piece.role == "day")
    title_piece = next(piece for piece in row if piece.role == "title")
    assert day_piece.rect.right + mockup.TIME_GAP <= title_piece.rect.left


def test_short_all_day_title_keeps_journee():
    day = NOW.date() + timedelta(days=1)
    laid = mockup.layout_agenda([_all_day(day, "Souper")], NOW, PANEL)
    row = [piece for piece in laid.pieces if piece.day_offset == 1]
    assert [piece.text for piece in row if piece.role == "time"] == ["Journée"]
    assert [piece.text for piece in row if piece.role == "title"] == ["Souper"]


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
    _header, time_font, title_font, next_font = laid.fonts
    title = next(piece for piece in laid.pieces if piece.role == "title")
    clock = next(piece for piece in laid.pieces if piece.zone == "today" and piece.role == "time")
    assert title.rect.width == title_font.size(title.text)[0]
    assert clock.rect.width == time_font.size(clock.text)[0]
    assert not title_font.get_bold()
    assert not next_font.get_bold()
    assert time_font.get_bold()
    assert next_font.get_height() == title_font.get_height()
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


def test_strip_is_the_transit_column_and_days_follow_today():
    from weatherdress import display

    events = [
        mockup.Event(
            datetime(2026, 11, 4, 11, 0),
            datetime(2026, 11, 4, 12, 0),
            "Piano",
        )
    ]
    tall = pygame.Rect(20, 40, 420, 320)
    laid = mockup.layout_agenda(events, NOW, tall)
    assert laid.strip_w == min(display.TRANSIT_STRIP_WIDTH, tall.w // 3)
    assert all(piece.rect.left >= laid.panel.x + laid.strip_w for piece in laid.pieces)
    today_bottom = max(piece.rect.bottom for piece in laid.pieces if piece.zone == "today")
    upcoming = [piece for piece in laid.pieces if piece.role == "day"]
    day_tops = [piece.rect.top for piece in upcoming]
    assert day_tops[1] - day_tops[0] == day_tops[2] - day_tops[1]
    tops = sorted({piece.rect.top for piece in laid.pieces})
    steps = [tops[index + 1] - tops[index] for index in range(len(tops) - 1)]
    assert max(steps) == min(steps)
    last_bottom = max(piece.rect.bottom for piece in laid.pieces)
    assert upcoming[0].rect.top > today_bottom
    assert laid.panel.bottom - last_bottom <= 20
    assert laid.fonts[3].get_height() == laid.fonts[2].get_height()
    screen = pygame.Surface((500, 400))
    screen.fill((10, 20, 30))
    mockup.paint_agenda(screen, laid)
    strip = pygame.Rect(laid.panel.x, laid.panel.y, laid.strip_w, laid.panel.h)
    blue = screen.get_at((strip.x + 4, strip.y + 10))
    assert abs(blue.r - display.TRANSIT_CARD_STRIP_BUS[0]) < 8
    assert abs(blue.g - display.TRANSIT_CARD_STRIP_BUS[1]) < 8
    assert abs(blue.b - display.TRANSIT_CARD_STRIP_BUS[2]) < 8
    found_white = False
    cx, cy = strip.center
    for y in range(cy - 16, cy + 16):
        for x in range(cx - 16, cx + 16):
            pixel = screen.get_at((x, y))
            if pixel.r > 220 and pixel.g > 220 and pixel.b > 220:
                found_white = True
    assert found_white


def test_type_and_spacing_follow_the_event_count():
    one = [
        mockup.Event(
            datetime(2026, 11, 4, 11, 0),
            datetime(2026, 11, 4, 12, 0),
            "Piano",
        )
    ]
    none_today = [
        mockup.Event(
            datetime(2026, 11, 5, 9, 0),
            datetime(2026, 11, 5, 10, 0),
            "Dentiste",
        ),
        mockup.Event(
            datetime(2026, 11, 5, 14, 0),
            datetime(2026, 11, 5, 15, 0),
            "Réunion",
        ),
    ]
    several = []
    for hour in (10, 11, 13, 15, 17, 20):
        start = datetime(2026, 11, 4, hour, 0)
        several.append(mockup.Event(start, start + timedelta(hours=1), f"Cours {hour}"))
    several.append(
        mockup.Event(
            datetime(2026, 11, 5, 9, 0),
            datetime(2026, 11, 5, 10, 0),
            "Dentiste",
        )
    )
    quiet = mockup.layout_agenda(none_today, NOW, PANEL)
    single = mockup.layout_agenda(one, NOW, PANEL)
    busy = mockup.layout_agenda(several, NOW, PANEL)
    assert quiet.panel == single.panel == busy.panel
    assert any(piece.text == "—" and piece.zone == "today" for piece in quiet.pieces)
    assert quiet.fonts[3].get_height() == quiet.fonts[2].get_height()
    assert single.fonts[3].get_height() == single.fonts[2].get_height()
    assert busy.fonts[3].get_height() == busy.fonts[2].get_height()
    assert busy.fonts[3].get_height() >= int(max(quiet.fonts[3].get_height(), single.fonts[3].get_height()) * 0.7)
    today_titles = [piece for piece in busy.pieces if piece.zone == "today" and piece.role == "title"]
    assert len(today_titles) >= 2
    tomorrow = [piece for piece in quiet.pieces if piece.day_offset == 1 and piece.role == "title"]
    assert len(tomorrow) == 1
    assert any(piece.day_offset == 1 and piece.role == "more" and piece.text == "+1" for piece in quiet.pieces)
    for laid in (quiet, single, busy):
        assert all(laid.panel.contains(piece.rect) for piece in laid.pieces)
        last = max(piece.rect.bottom for piece in laid.pieces)
        assert laid.panel.bottom - last <= 20
        tops = sorted({piece.rect.top for piece in laid.pieces})
        steps = [tops[index + 1] - tops[index] for index in range(len(tops) - 1)]
        assert max(steps) == min(steps)
    short_panel = pygame.Rect(20, 40, 340, 150)
    tall_panel = pygame.Rect(20, 40, 560, 320)
    short = mockup.layout_agenda(one, NOW, short_panel)
    tall = mockup.layout_agenda(one, NOW, tall_panel)
    assert tall.fonts[3].get_height() > short.fonts[3].get_height()


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

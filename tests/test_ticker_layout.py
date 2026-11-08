"""Le bandeau bas réserve sa place sans changer les polices ni déborder."""

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

from weatherdress import display  # noqa: E402
from weatherdress import ticker  # noqa: E402
from weatherdress.calendar_feed import CalendarOccurrence  # noqa: E402
from weatherdress.paths import IMAGES_DIR  # noqa: E402

TZ = ZoneInfo("America/Toronto")
NOW = datetime(2026, 11, 4, 9, 30, tzinfo=TZ)
SIZE = (800, 480)

DEPARTURES = {
    "bus": {
        "56220": {"route": "51", "label": "Snowdon", "minutes": [4, 12]},
        "56221": {"route": "160", "label": "St-Michel", "minutes": [8, 18]},
    },
    "metro": {
        "Station Snowdon": [3, 9],
        "Station Saint-Michel": [5, 11],
    },
}


def _config(*, ticker_on=False, ticker_text="", transit=True, calendar=False):
    data = {
        "screen_width": 800,
        "screen_height": 480,
        "use_weather_background": False,
        "use_ambient_weather_background": False,
        "background_color": [255, 255, 255],
        "circle_background_color": [230, 230, 230],
        "language": "fr",
        "units": "metric",
        "layout": {
            "weather_temp_font_min": 72,
            "weather_temp_font_max": 152,
            "weather_desc_font_min": 32,
            "weather_desc_font_max": 48,
        },
    }
    if transit:
        data["transit"] = {
            "gtfs_url": "https://example.test/gtfs.zip",
            "metro_station": "Outremont",
            "metro_route_id": "5",
            "bus_stops": {"56220": "Snowdon", "56221": "St-Michel"},
            "metro_directions": {
                "Station Snowdon": "Snowdon",
                "Station Saint-Michel": "St-Michel",
            },
            "card_title_font_px": 50,
            "card_subtitle_font_px": 32,
            "card_times_font_px": 60,
        }
    if calendar:
        data["calendar"] = {
            "enabled": True,
            "url": "",
            "refresh_minutes": 30,
            "rotate_seconds": 15,
        }
    if ticker_on:
        block = {"enabled": True, "height_px": 32}
        if ticker_text:
            block["text"] = ticker_text
        data["ticker"] = block
    return data


def _outfit():
    return {
        "character": "normal_woman1",
        "current_accessories": ["scarf"],
        "future_accessories": [
            {"accessory": "umbrella", "hour": 15, "hours_from_now": 2},
        ],
    }


def _weather():
    return {
        "temp": 3.0,
        "description": "ciel dégagé",
        "condition_id": 800,
        "icon": "01d",
        "clouds": 8,
        "hour": 9,
        "wind_kmh": 12,
        "rain": 0,
        "snow": 0,
    }


def _events():
    start = datetime(2026, 11, 4, 11, 15, tzinfo=TZ)
    later = datetime(2026, 11, 5, 9, 0, tzinfo=TZ)
    return [
        CalendarOccurrence(start, start + timedelta(hours=1), "Cours de natation", False),
        CalendarOccurrence(later, later + timedelta(hours=1), "Dentiste", False),
    ]


def _paint(config, *, phase=0.0, events=None, calendar_phase=0.0, monkeypatch):
    monkeypatch.setattr(pygame.display, "flip", lambda: None)
    screen = pygame.Surface(SIZE)
    metrics = {}
    display.render(
        screen,
        _outfit(),
        _weather(),
        IMAGES_DIR,
        config,
        transit_data=DEPARTURES if "transit" in config else None,
        transit_phase_t=0.0,
        calendar_events=events,
        calendar_phase_t=calendar_phase,
        ticker_phase_t=phase,
        shown_at=NOW,
        frame_metrics=metrics,
    )
    return screen, metrics


def _above_band(screen, band_h):
    height = screen.get_height() - band_h
    return pygame.image.tostring(screen.subsurface((0, 0, screen.get_width(), height)), "RGB")


def test_band_font_fills_the_strip():
    px = ticker.band_font_px(32)
    assert px >= 26
    height = pygame.font.SysFont("sans-serif", px, bold=True).get_height()
    assert height <= 28


def test_cached_text_surface_is_reused():
    first = ticker.cached_text_surface("Bonjour", 20)
    assert ticker.cached_text_surface("Bonjour", 20) is first
    assert ticker.cached_text_surface("Bonsoir", 20) is not first


def test_scene_stamp_ignores_the_ticker_clock():
    from weatherdress.main import scene_stamp

    config = {
        "transit": {"transit_alternate_seconds": 5},
        "calendar": {"rotate_seconds": 15},
    }
    common = dict(
        config=config,
        weather={"temp": 3},
        outfit={"character": "normal_woman1"},
        transit={"bus": {"1": {"minutes": [4, 12]}}},
        events=(),
        notice=None,
        debug_label=None,
        size=(800, 480),
    )
    assert scene_stamp(**common, now=1_000) == scene_stamp(**common, now=1_000.4)
    assert scene_stamp(**common, now=1_000) == scene_stamp(**common, now=1_005)
    changed = dict(common)
    changed["weather"] = {"temp": 4}
    assert scene_stamp(**common, now=1_000) != scene_stamp(**changed, now=1_000)


def test_shown_surface_keeps_a_ready_view():
    from weatherdress.main import shown_surface

    bus = pygame.Surface((8, 8))
    agenda = pygame.Surface((8, 8))
    cache = {(0, 0): bus, (0, 1): agenda}
    assert shown_surface(cache, (0, 0), (8, 8)) is bus
    assert shown_surface(cache, (1, 0), (8, 8)) is bus
    assert shown_surface({}, (0, 0), (8, 8)) is None
    assert shown_surface(cache, (0, 0), (4, 4)) is None


def test_scene_cache_builder_returns_without_waiting():
    import time

    from weatherdress.main import SceneCacheBuilder

    builder = SceneCacheBuilder()
    try:
        started = time.perf_counter()

        def slow():
            time.sleep(0.2)
            return {(0, 0): "bus"}

        builder.request("horaires", slow)
        assert builder.poll() is None
        assert time.perf_counter() - started < 0.15
        ready = None
        deadline = time.perf_counter() + 1
        while time.perf_counter() < deadline:
            ready = builder.poll()
            if ready is not None:
                break
            time.sleep(0.01)
        assert ready == ("horaires", {(0, 0): "bus"})
    finally:
        builder.close()


def test_agenda_and_transit_share_one_catalog():
    from weatherdress.main import current_view, view_catalog

    moment = datetime.now().astimezone()
    start = moment + timedelta(hours=2)
    events = (CalendarOccurrence(start, start + timedelta(hours=1), "Cours", False),)
    config = {
        "transit": {
            "transit_alternate_seconds": 5,
            "gtfs_url": "x",
            "metro_station": "O",
            "metro_route_id": "1",
        },
        "calendar": {"enabled": True, "rotate_seconds": 15},
    }
    transit = {"bus": {"1": {"minutes": [4]}}, "metro": {"A": [3]}}
    catalog = view_catalog(config, transit, events)
    assert (0, 0) in catalog
    assert (0, 1) in catalog
    leaving = current_view(config, transit, events, 1_000)
    coming_back = current_view(config, transit, events, 1_015)
    assert leaving in catalog
    assert coming_back in catalog
    assert leaving[1] != coming_back[1]


def test_transit_alternate_reuses_two_cached_views():
    from weatherdress.main import current_view, view_catalog

    config = {"transit": {"transit_alternate_seconds": 5, "gtfs_url": "x", "metro_station": "O", "metro_route_id": "1"}}
    transit = {
        "bus": {"1": {"minutes": [4]}, "2": {"minutes": [8]}},
        "metro": {"A": [3], "B": [5]},
    }
    catalog = view_catalog(config, transit, ())
    assert catalog == ((0, 0), (1, 0))
    assert current_view(config, transit, (), 1_000) in catalog
    assert current_view(config, transit, (), 1_000) != current_view(config, transit, (), 1_005)
    assert current_view(config, transit, (), 1_000) == current_view(config, transit, (), 1_010)


def test_new_phrase_keeps_the_pixel_already_reached():
    state = {}
    assert ticker.carry_offset(10, 40, 300, "ancienne", state) == 100
    assert ticker.carry_offset(10, 40, 80, "nouvelle", state) == 100 % 80
    assert ticker.carry_offset(11, 40, 80, "nouvelle", state) == (100 + 40) % 80


def test_scroll_offset_advances_left_and_wraps():
    assert ticker.band_height({}) == 0
    assert ticker.band_height({"ticker": {"enabled": False}}) == 0
    assert ticker.band_height({"ticker": {"enabled": True}}) == ticker.DEFAULT_HEIGHT
    assert ticker.scroll_offset(0, 40, 100) == 0
    assert ticker.scroll_offset(1, 40, 100) == 40
    assert ticker.scroll_offset(3, 40, 100) == 20
    assert ticker.scroll_offset(5, 40, 100) == 0
    assert ticker.scroll_offset(-2, 40, 100) == 0
    assert ticker.scroll_offset(4, 40, 0) == 0
    assert ticker.scroll_offset(2, 40, 500) > ticker.scroll_offset(1, 40, 500)


def test_disabled_ticker_keeps_the_full_screen(monkeypatch):
    _screen, metrics = _paint(_config(), monkeypatch=monkeypatch)
    assert metrics["ticker_band"] == 0
    assert metrics["content_bottom"] == 476
    assert metrics["transit_row_count"] == 2


def _without_enlarged_fonts(config):
    config["layout"] = {}
    transit = config.get("transit")
    if isinstance(transit, dict):
        for key in (
            "card_title_font_px",
            "card_subtitle_font_px",
            "card_times_font_px",
        ):
            transit.pop(key, None)
    return config


def test_default_fonts_keep_both_cards_above_the_band(monkeypatch):
    off_cfg = _without_enlarged_fonts(_config())
    on_cfg = _without_enlarged_fonts(_config(ticker_on=True))
    _off_screen, off = _paint(off_cfg, monkeypatch=monkeypatch)
    _on_screen, on = _paint(on_cfg, monkeypatch=monkeypatch)

    assert on["ticker_band"] == 32
    assert on["content_bottom"] == 444
    assert on["character_bottom"] <= on["content_bottom"]
    assert on["weather_bottom"] <= on["content_bottom"]
    assert on["panel"] is not None
    assert on["panel"].bottom <= on["content_bottom"]
    assert on["transit_row_count"] == off["transit_row_count"] == 2
    assert on["character_centerx"] == off["character_centerx"]
    assert on["weather_temp_px"] == off["weather_temp_px"]
    assert on["weather_desc_px"] == off["weather_desc_px"]
    assert on["character_height"] < off["character_height"]


def test_enlarged_transit_cards_drop_one_row_under_the_band(monkeypatch):
    """Les cartes agrandies remplissent déjà l'écran : 32 px en bas en retire une."""
    _off_screen, off = _paint(_config(), monkeypatch=monkeypatch)
    _on_screen, on = _paint(_config(ticker_on=True), monkeypatch=monkeypatch)

    assert off["transit_row_count"] == 2
    assert on["transit_row_count"] == 1
    assert on["content_bottom"] == 444
    assert on["character_bottom"] <= on["content_bottom"]
    assert on["weather_bottom"] <= on["content_bottom"]
    assert on["panel"].bottom <= on["content_bottom"]
    assert on["character_centerx"] == off["character_centerx"]
    assert on["weather_temp_px"] == off["weather_temp_px"]
    assert on["weather_desc_px"] == off["weather_desc_px"]


def test_agenda_panel_stops_above_the_band(monkeypatch):
    screen, metrics = _paint(
        _config(ticker_on=True, transit=False, calendar=True),
        events=_events(),
        calendar_phase=15,
        monkeypatch=monkeypatch,
    )
    assert metrics["side"] == "calendar"
    assert metrics["panel"] is not None
    assert metrics["panel"].bottom <= metrics["content_bottom"]
    assert screen.get_at((10, 479))[:3] == ticker.BAND_BG


def _with_fitted_cards(config):
    """Titre 40 et sous-titre 22 : la carte retombe vers 90 px."""
    config["transit"]["card_title_font_px"] = 40
    config["transit"]["card_subtitle_font_px"] = 22
    return config


def test_fitted_cards_keep_bus_and_metro_above_the_black_band(monkeypatch):
    cfg = _with_fitted_cards(_config(ticker_on=True))
    screen, metrics = _paint(cfg, monkeypatch=monkeypatch)
    assert display.transit_card_layout(cfg)["card_height"] <= 92
    assert metrics["ticker_band"] == 32
    assert metrics["transit_row_count"] == 2
    assert metrics["panel"] is not None
    assert metrics["panel"].bottom <= metrics["content_bottom"]
    assert metrics["character_bottom"] <= metrics["content_bottom"]
    assert metrics["weather_bottom"] <= metrics["content_bottom"]
    assert screen.get_at((400, 470))[:3] == ticker.BAND_BG


def test_empty_band_stays_black_and_leaves_the_scene_still(monkeypatch):
    early, early_metrics = _paint(
        _with_fitted_cards(_config(ticker_on=True)), phase=0.0, monkeypatch=monkeypatch
    )
    later, _later_metrics = _paint(
        _with_fitted_cards(_config(ticker_on=True)), phase=4.0, monkeypatch=monkeypatch
    )
    assert early_metrics["transit_row_count"] == 2
    assert pygame.image.tostring(early, "RGB") == pygame.image.tostring(later, "RGB")
    assert early.get_at((0, 479))[:3] == ticker.BAND_BG
    assert early.get_at((799, 450))[:3] == ticker.BAND_BG


def test_only_the_band_moves_between_two_instants(monkeypatch):
    text = ticker.SAMPLE_TEXT
    early, early_metrics = _paint(
        _config(ticker_on=True, ticker_text=text), phase=0.0, monkeypatch=monkeypatch
    )
    later, later_metrics = _paint(
        _config(ticker_on=True, ticker_text=text), phase=4.0, monkeypatch=monkeypatch
    )
    assert early_metrics["character_bottom"] == later_metrics["character_bottom"]
    assert early_metrics["panel"] == later_metrics["panel"]
    assert _above_band(early, 32) == _above_band(later, 32)
    assert pygame.image.tostring(early, "RGB") != pygame.image.tostring(later, "RGB")

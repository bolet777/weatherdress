"""
Régression : display.render(outfit=…) ne doit pas masquer le module outfit
(dict n'a pas accessory_badge_offset).
"""
import os

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")

import pytest  # noqa: E402
import pygame  # noqa: E402

pytest.importorskip("pygame")

pygame.init()

from weatherdress import display  # noqa: E402


def _minimal_config():
    return {
        "screen_width": 800,
        "screen_height": 480,
        "use_weather_background": False,
        "use_ambient_weather_background": False,
        "background_color": [255, 255, 255],
        "circle_background_color": [230, 230, 230],
        "language": "fr",
        "units": "metric",
        "layout": {},
    }


def test_plan_right_column_vertical_layout_centers_on_character():
    char_rect = pygame.Rect(0, 0, 100, 360)
    char_rect.centery = 250
    row_stride = display.TRANSIT_CARD_HEIGHT + display.TRANSIT_CARD_GAP
    two_rows = [
        ("bus", "Bus 1", "Stop", [], (0, 0, 0)),
        ("metro", "Station X", "Direction Y", [], (0, 0, 0)),
    ]
    weather_h = 88
    transit_h = display.transit_panel_content_height(two_rows, row_stride)
    w_top, t_top = display.plan_right_column_vertical_layout(
        char_rect, weather_h, transit_h, 480, 70, 0
    )
    total = weather_h + display.TRANSIT_AFTER_WEATHER_GAP + transit_h
    block_center = w_top + total / 2.0
    assert abs(block_center - char_rect.centery) < 1.5
    assert t_top == w_top + weather_h + display.TRANSIT_AFTER_WEATHER_GAP


def test_resolve_transit_panel_start_y_aligns_on_character_feet():
    char_rect = pygame.Rect(0, 0, 100, 400)
    char_rect.midbottom = (200, 460)
    rows = [("bus", "Bus 1", "Stop", [], (0, 0, 0))]
    row_stride = display.TRANSIT_CARD_HEIGHT + display.TRANSIT_CARD_GAP
    start_y = display.resolve_transit_panel_start_y(
        char_rect, rows, row_stride, 480
    )
    assert start_y == 460 - display.TRANSIT_CARD_HEIGHT
    bottom = start_y + display.transit_panel_content_height(rows, row_stride)
    assert bottom == char_rect.bottom


def test_display_top_safe_margin_grows_with_screen():
    small = display.display_top_safe_margin(480)
    large = display.display_top_safe_margin(900)
    assert large > small


def test_transit_max_rows_allows_bus_and_metro_when_anchored_on_feet():
    row_stride = display.TRANSIT_CARD_HEIGHT + display.TRANSIT_CARD_GAP
    char_rect = pygame.Rect(0, 0, 120, 380)
    char_rect.midbottom = (240, 476)
    two_rows = [
        ("bus", "Bus 161", "St-Michel", [15, 27], (0, 0, 0)),
        ("metro", "Station Outremont", "Direction Snowdon", [], (0, 0, 0)),
    ]
    start_y = display.resolve_transit_panel_start_y(
        char_rect, two_rows, row_stride, 480
    )
    assert start_y is not None
    max_rows = display.transit_max_rows_from_start_y(480, start_y, row_stride)
    assert max_rows >= 2
    bottom = start_y + display.transit_panel_content_height(two_rows, row_stride)
    assert bottom <= char_rect.bottom


def test_transit_card_layout_defaults():
    layout = display.transit_card_layout({})
    assert layout["title_px"] == display.TRANSIT_CARD_TITLE_PX
    assert layout["card_height"] == display.TRANSIT_CARD_HEIGHT
    assert layout["row_stride"] == display.TRANSIT_CARD_HEIGHT + display.TRANSIT_CARD_GAP


def test_transit_card_layout_custom_fonts_and_height():
    cfg = {
        "transit": {
            "card_title_font_px": 28,
            "card_subtitle_font_px": 20,
            "card_times_font_px": 30,
            "strip_mode_letter_font_px": 50,
            "card_height_px": 96,
        }
    }
    layout = display.transit_card_layout(cfg)
    assert layout["title_px"] == 28
    assert layout["times_px"] == 30
    assert layout["strip_letter_px"] == 50
    assert layout["card_height"] == 96
    assert layout["row_stride"] == 96 + display.TRANSIT_CARD_GAP


def test_transit_panel_build_rows_keeps_metro_when_start_y_is_low():
    row_stride = display.TRANSIT_CARD_HEIGHT + display.TRANSIT_CARD_GAP
    char_rect = pygame.Rect(0, 0, 120, 380)
    char_rect.midbottom = (240, 476)
    two_rows = [
        ("bus", "Bus 161", "St-Michel", [15, 27], (0, 0, 0)),
        ("metro", "Station Outremont", "Direction Snowdon", [], (0, 0, 0)),
    ]
    start_y = display.resolve_transit_panel_start_y(
        char_rect, two_rows, row_stride, 480
    )
    cfg = {
        "transit": {
            "stm_api_key": "k",
            "gtfs_url": "https://example.com/gtfs.zip",
            "bus_stops": {"1": "St-Michel"},
            "metro_station": "Outremont",
            "metro_directions": {"Snowdon": "Snowdon"},
        }
    }
    data = {
        "bus": {"1": {"route": "161", "label": "St-Michel", "minutes": [15, 27]}},
        "metro": {"Snowdon": []},
    }
    rows, stride = display._transit_panel_build_rows(
        data, cfg, screen_h=480, start_y=start_y, transit_phase_t=0.0
    )
    assert len(rows) == 2
    assert rows[1][0] == "metro"


def test_render_future_accessories_column_runs_without_crash(tmp_path, monkeypatch):
    """Exerce accessoires futurs (colonne + pastilles heure)."""
    monkeypatch.setattr(pygame.display, "flip", lambda: None)

    surf = pygame.Surface((32, 32), pygame.SRCALPHA)

    def fake_load_image(_path):
        return surf.copy()

    monkeypatch.setattr(display, "load_image", fake_load_image)

    screen = pygame.Surface((800, 480))
    cfg = _minimal_config()
    outfit_data = {
        "character": "normal_woman1",
        "current_accessories": [],
        "future_accessories": [
            {"accessory": "umbrella", "hour": 15, "hours_from_now": 2},
        ],
    }
    weather = {
        "temp": 18.0,
        "description": "Test",
        "condition_id": 801,
        "icon": "02d",
    }

    display.render(
        screen,
        outfit_data,
        weather,
        str(tmp_path),
        cfg,
        transit_data=None,
        transit_phase_t=0.0,
    )


def test_render_accessories_column_includes_current_chips(tmp_path, monkeypatch):
    """Accessoires actuels passent par la colonne (plus de blit plein personnage)."""
    monkeypatch.setattr(pygame.display, "flip", lambda: None)

    surf = pygame.Surface((32, 32), pygame.SRCALPHA)

    def fake_load_image(_path):
        return surf.copy()

    monkeypatch.setattr(display, "load_image", fake_load_image)

    screen = pygame.Surface((800, 480))
    cfg = _minimal_config()
    outfit_data = {
        "character": "normal_woman1",
        "current_accessories": ["cap"],
        "future_accessories": [
            {"accessory": "umbrella", "hour": 15, "hours_from_now": 2},
        ],
    }
    weather = {
        "temp": 18.0,
        "description": "Test",
        "condition_id": 801,
        "icon": "02d",
    }

    display.render(
        screen,
        outfit_data,
        weather,
        str(tmp_path),
        cfg,
        transit_data=None,
        transit_phase_t=0.0,
    )

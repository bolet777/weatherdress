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

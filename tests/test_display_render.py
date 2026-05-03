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


def test_render_future_accessory_runs_badge_offset_lookup(tmp_path, monkeypatch):
    """Exerce accessoires futurs + pastille (outfit_module.accessory_badge_offset)."""
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

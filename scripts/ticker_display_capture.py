"""Captures 800×480 du bandeau bas, avec et sans réservation.

Données fictives. La config locale (polices, fond) est reprise telle quelle.
Le bandeau n'est activé que dans ces images.

    PYTHONPATH=src python3 scripts/ticker_display_capture.py cache/ticker_display
"""

from __future__ import annotations

import copy
import os
import sys
from datetime import datetime

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

import pygame  # noqa: E402

from weatherdress import display  # noqa: E402
from weatherdress.config_file import load_config  # noqa: E402
from weatherdress.paths import IMAGES_DIR  # noqa: E402

sys.path.insert(0, os.path.dirname(__file__))
from calendar_mockup import (  # noqa: E402
    FAKE_TRANSIT,
    events_for_scenario,
    sample_outfit,
    sample_weather,
)

NOW = datetime(2026, 11, 4, 9, 30)
SIZE = (800, 480)


def _scene(config, *, ticker_on, transit, rotate, phase, stock_fonts=False):
    scene = copy.deepcopy(config)
    scene["screen_width"], scene["screen_height"] = SIZE
    scene["fullscreen"] = False
    if stock_fonts:
        scene["layout"] = {}
        transit_block = dict(scene.get("transit") or {})
        for key in (
            "card_title_font_px",
            "card_subtitle_font_px",
            "card_times_font_px",
        ):
            transit_block.pop(key, None)
        scene["transit"] = transit_block
    block = dict(scene.get("calendar") or {})
    block["enabled"] = True
    block["rotate_seconds"] = rotate
    scene["calendar"] = block
    if ticker_on:
        scene["ticker"] = {
            "enabled": True,
            "height_px": 32,
            "speed_px_per_sec": 48,
        }
    else:
        scene.pop("ticker", None)
    if not transit:
        transit_block = dict(scene.get("transit") or {})
        transit_block.pop("gtfs_url", None)
        scene["transit"] = transit_block
    return scene


def export(directory, config=None):
    if config is None:
        config = load_config()
    os.makedirs(directory, exist_ok=True)
    pygame.init()
    pygame.display.set_mode(SIZE)
    pygame.display.flip = lambda: None
    outfit = sample_outfit()
    weather = sample_weather(NOW)
    typical = events_for_scenario("journee-type", NOW)
    busy = events_for_scenario("journee-chargee", NOW)
    shots = (
        ("01-transport-sans-bande", False, True, 15, 0, 0.0, typical),
        ("02-transport-bande-t0", True, True, 15, 0, 0.0, typical),
        ("03-transport-bande-t4", True, True, 15, 0, 4.0, typical),
        ("04-agenda-bande", True, True, 15, 15, 0.0, typical),
        ("05-agenda-seul-bande", True, False, 0, 0, 0.0, typical),
        ("06-journee-chargee-bande", True, True, 15, 15, 2.0, busy),
        ("07-polices-defaut-sans-bande", False, True, 15, 0, 0.0, typical),
        ("08-polices-defaut-bande-t0", True, True, 15, 0, 0.0, typical),
    )
    lines = []
    paths = []
    for name, ticker_on, transit, rotate, calendar_phase, ticker_phase, events in shots:
        scene = _scene(
            config,
            ticker_on=ticker_on,
            transit=transit,
            rotate=rotate,
            phase=calendar_phase,
            stock_fonts=name.startswith("07") or name.startswith("08"),
        )
        screen = pygame.Surface(SIZE)
        metrics = {}
        display.render(
            screen,
            outfit,
            weather,
            IMAGES_DIR,
            scene,
            transit_data=FAKE_TRANSIT if transit else None,
            transit_phase_t=0.0,
            calendar_events=events,
            calendar_phase_t=calendar_phase,
            ticker_phase_t=ticker_phase,
            shown_at=NOW,
            frame_metrics=metrics,
        )
        path = os.path.join(directory, f"{name}.png")
        pygame.image.save(screen, path)
        paths.append(path)
        panel = metrics.get("panel")
        panel_bottom = None if panel is None else panel.bottom
        lines.append(
            f"{name}: side={metrics.get('side')} "
            f"band={metrics.get('ticker_band')} "
            f"content_bottom={metrics.get('content_bottom')} "
            f"character={metrics.get('character_width')}x{metrics.get('character_height')} "
            f"centerx={metrics.get('character_centerx')} "
            f"character_bottom={metrics.get('character_bottom')} "
            f"weather_bottom={metrics.get('weather_bottom')} "
            f"panel_bottom={panel_bottom} "
            f"column_left={metrics.get('column_left')} "
            f"transit_rows={metrics.get('transit_row_count')} "
            f"temp_px={metrics.get('weather_temp_px')} "
            f"desc_px={metrics.get('weather_desc_px')}"
        )
    report = os.path.join(directory, "mesures.txt")
    with open(report, "w", encoding="utf-8") as handle:
        handle.write("\n".join(lines) + "\n")
    paths.append(report)
    return paths


def main(argv=None):
    directory = (argv or sys.argv[1:] or ["cache/ticker_display"])[0]
    for path in export(directory):
        print(path)
    return 0


if __name__ == "__main__":
    sys.exit(main())

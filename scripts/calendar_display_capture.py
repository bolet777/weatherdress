"""Captures 800×480 de l'agenda branché sur le rendu Pygame.

Événements fictifs, départs fictifs. Aucun appel iCloud ni STM.

    PYTHONPATH=src python3 scripts/calendar_display_capture.py cache/calendar_display
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

sys.path.insert(0, os.path.join(os.path.dirname(__file__)))
from calendar_mockup import (  # noqa: E402
    FAKE_TRANSIT,
    events_for_scenario,
    sample_outfit,
    sample_weather,
)

NOW = datetime(2026, 11, 4, 9, 30)
SIZE = (800, 480)


def _scene(config, *, transit, rotate, phase, events):
    scene = copy.deepcopy(config)
    scene["screen_width"], scene["screen_height"] = SIZE
    block = dict(scene.get("calendar") or {})
    block["enabled"] = True
    block["rotate_seconds"] = rotate
    scene["calendar"] = block
    if not transit:
        transit_block = dict(scene.get("transit") or {})
        transit_block.pop("gtfs_url", None)
        scene["transit"] = transit_block
    return scene, events, phase


def captures(config):
    typical = events_for_scenario("journee-type", NOW)
    busy = events_for_scenario("journee-chargee", NOW)
    quiet = events_for_scenario("aujourd-hui-vide", NOW)
    return (
        ("01-transport", _scene(config, transit=True, rotate=15, phase=0, events=typical)),
        ("02-agenda", _scene(config, transit=True, rotate=15, phase=15, events=typical)),
        ("03-sans-evenement", _scene(config, transit=True, rotate=15, phase=15, events=[])),
        ("04-rotation-coupee", _scene(config, transit=True, rotate=0, phase=40, events=typical)),
        ("05-agenda-seul", _scene(config, transit=False, rotate=0, phase=0, events=typical)),
        ("06-sans-transport", _scene(config, transit=False, rotate=15, phase=15, events=[])),
        ("07-debordement", _scene(config, transit=True, rotate=15, phase=15, events=busy)),
        ("08-aujourd-hui-vide", _scene(config, transit=True, rotate=15, phase=15, events=quiet)),
    )


def export(directory, config=None):
    if config is None:
        config = load_config()
    os.makedirs(directory, exist_ok=True)
    pygame.init()
    pygame.display.set_mode(SIZE)
    pygame.display.flip = lambda: None
    outfit = sample_outfit()
    weather = sample_weather(NOW)
    paths = []
    for name, (scene, events, phase) in captures(config):
        screen = pygame.Surface(SIZE)
        display.render(
            screen,
            outfit,
            weather,
            IMAGES_DIR,
            scene,
            transit_data=FAKE_TRANSIT if scene.get("transit", {}).get("gtfs_url") else None,
            transit_phase_t=0.0,
            calendar_events=events,
            calendar_phase_t=phase,
            shown_at=NOW,
        )
        path = os.path.join(directory, f"{name}.png")
        pygame.image.save(screen, path)
        paths.append(path)
    return paths


def main(argv=None):
    directory = (argv or sys.argv[1:] or ["cache/calendar_display"])[0]
    for path in export(directory):
        print(path)
    return 0


if __name__ == "__main__":
    sys.exit(main())

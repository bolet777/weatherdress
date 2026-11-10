"""Inter embarqué : une graisse par rôle, chiffres tabulaires pour l'heure."""

import os

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

import pygame  # noqa: E402
import pytest  # noqa: E402

pytest.importorskip("pygame")

pygame.init()

from weatherdress import fonts  # noqa: E402


def test_each_role_loads_its_own_file():
    loaded = [fonts.load(32, role) for role in fonts.ROLES]
    assert len({id(font) for font in loaded}) == len(loaded)
    assert [fonts.role_of(font) for font in loaded] == list(fonts.ROLES)


def test_clock_strings_keep_the_same_width():
    tabular = fonts.load(72, "semibold-tabular")
    widths = [tabular.size(text)[0] for text in ("00:00", "11:11", "23:59")]
    assert len(set(widths)) == 1
    proportional = fonts.load(72, "semibold")
    assert len({proportional.size(digit)[0] for digit in "0123456789"}) > 1

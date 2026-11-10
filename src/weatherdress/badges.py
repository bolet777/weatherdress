"""Pastilles d'annotation (heure d'accessoire, etc.)."""

import pygame

from . import fonts

BADGE_BG_COLOR = (220, 50, 50)
BADGE_TEXT_COLOR = (255, 255, 255)
BADGE_AA_SCALE = 3  # sur-échantillon : cercle HR puis lissage

# Petits écrans : Medium, assez présent pour rester lisible de loin.
BADGE_FONT_PX = 18
BADGE_PADDING = 7


def draw_badge(surface, text, center):
    """Dessine une pastille ronde avec le texte centré."""
    font = fonts.load(BADGE_FONT_PX, "medium")
    text_surf = font.render(text, True, BADGE_TEXT_COLOR)
    padding = BADGE_PADDING
    radius = max(text_surf.get_width(), text_surf.get_height()) // 2 + padding

    scale = BADGE_AA_SCALE
    hi = pygame.Surface(
        (radius * 2 * scale, radius * 2 * scale), pygame.SRCALPHA
    )
    c = radius * scale
    pygame.draw.circle(hi, BADGE_BG_COLOR, (c, c), radius * scale)
    badge_surf = pygame.transform.smoothscale(hi, (radius * 2, radius * 2))

    badge_surf.blit(
        text_surf,
        (
            radius - text_surf.get_width() // 2,
            radius - text_surf.get_height() // 2,
        ),
    )
    surface.blit(badge_surf, (center[0] - radius, center[1] - radius))

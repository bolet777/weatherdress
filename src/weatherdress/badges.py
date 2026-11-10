"""Pastilles d'annotation (heure d'accessoire, etc.)."""

import pygame

from . import fonts

BADGE_BG_COLOR = (232, 78, 72, 222)
BADGE_TEXT_COLOR = (255, 255, 255)
BADGE_AA_SCALE = 3  # sur-échantillon : forme HR puis lissage

# Petits écrans : Medium, assez présent pour rester lisible de loin.
BADGE_FONT_PX = 18
BADGE_PADDING = 7


def draw_badge(surface, text, center):
    """Pastille heure : capsule aux coins arrondis, fond légèrement translucide."""
    font = fonts.load(BADGE_FONT_PX, "medium")
    text_surf = font.render(text, True, BADGE_TEXT_COLOR)
    pad_x = BADGE_PADDING + 1
    pad_y = max(3, BADGE_PADDING - 3)
    width = text_surf.get_width() + pad_x * 2
    height = text_surf.get_height() + pad_y * 2
    radius = height // 2

    scale = BADGE_AA_SCALE
    hi = pygame.Surface((width * scale, height * scale), pygame.SRCALPHA)
    hi.fill((*BADGE_BG_COLOR[:3], 0))
    pygame.draw.rect(
        hi,
        BADGE_BG_COLOR,
        hi.get_rect(),
        border_radius=radius * scale,
    )
    badge_surf = pygame.transform.smoothscale(hi, (width, height))

    badge_surf.blit(
        text_surf,
        (
            (width - text_surf.get_width()) // 2,
            (height - text_surf.get_height()) // 2,
        ),
    )
    surface.blit(
        badge_surf,
        (center[0] - width // 2, center[1] - height // 2),
    )

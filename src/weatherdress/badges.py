"""Pastilles d'annotation (heure d'accessoire, etc.)."""

import pygame

BADGE_BG_COLOR = (220, 50, 50)
BADGE_TEXT_COLOR = (255, 255, 255)
BADGE_AA_SCALE = 3  # sur-échantillon : cercle HR puis lissage

# Petits écrans : pas de gras (meilleure lisibilité des chiffres), taille suffisante.
BADGE_FONT_PX = 18
BADGE_PADDING = 7
# Ordre = préférence pygame (polices souvent nettes sur Linux embarqué / Pi).
BADGE_FONT_NAMES = (
    "arial",
    "liberation sans",
    "dejavu sans",
    "helvetica",
    "sans-serif",
)


def draw_badge(surface, text, center):
    """Dessine une pastille ronde avec le texte centré."""
    font = pygame.font.SysFont(
        ",".join(BADGE_FONT_NAMES), BADGE_FONT_PX, bold=False, italic=False
    )
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

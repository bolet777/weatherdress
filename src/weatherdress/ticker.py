"""Bandeau bas expérimental.

Désactivé tant que ``ticker.enabled`` n'est pas vrai. Sans texte, la bande
reste noire et vide. Le flux d'actualités viendra ensuite.
"""

import pygame

SAMPLE_TEXT = (
    "●  Essai de bandeau  ●  Le texte défile de droite à gauche  ●  "
    "Météo, transport et agenda restent au-dessus  ●  "
)
DEFAULT_HEIGHT = 32
DEFAULT_SPEED = 48
LOOP_GAP = 64
BAND_BG = (0, 0, 0)
BAND_FG = (248, 248, 248)


def settings(config):
    """Réglages du bandeau, ou None s'il ne doit pas apparaître."""
    block = config.get("ticker") if isinstance(config, dict) else None
    if not isinstance(block, dict) or block.get("enabled") is not True:
        return None
    try:
        height = int(block.get("height_px", DEFAULT_HEIGHT))
    except (TypeError, ValueError):
        height = DEFAULT_HEIGHT
    height = max(24, min(64, height))
    try:
        speed = float(block.get("speed_px_per_sec", DEFAULT_SPEED))
    except (TypeError, ValueError):
        speed = DEFAULT_SPEED
    if speed < 0:
        speed = 0.0
    text = block.get("text")
    if not isinstance(text, str):
        text = ""
    return {"height": height, "speed": speed, "text": text.strip()}


def band_height(config):
    spec = settings(config)
    if spec is None:
        return 0
    return spec["height"]


def scroll_offset(elapsed_s, speed_px_per_sec, period):
    """Pixels déjà parcourus vers la gauche, dans une période. Jamais négatif."""
    period = int(period)
    if period <= 0:
        return 0
    try:
        elapsed = float(elapsed_s)
        speed = float(speed_px_per_sec)
    except (TypeError, ValueError):
        return 0
    if elapsed < 0 or speed <= 0:
        return 0
    return int(elapsed * speed) % period


def paint(screen, config, elapsed_s):
    """Dessine le bandeau. Retourne son rectangle, ou None s'il est coupé."""
    spec = settings(config)
    if spec is None:
        return None
    screen_w, screen_h = screen.get_size()
    band_h = spec["height"]
    band = pygame.Rect(0, max(0, screen_h - band_h), screen_w, min(band_h, screen_h))
    pygame.draw.rect(screen, BAND_BG, band)
    if not spec["text"]:
        return band

    font_px = max(16, band_h - 12)
    font = pygame.font.SysFont("sans-serif", font_px, bold=False)
    text_surf = font.render(spec["text"], True, BAND_FG)
    period = text_surf.get_width() + LOOP_GAP
    offset = scroll_offset(elapsed_s, spec["speed"], period)
    y = band.y + (band.h - text_surf.get_height()) // 2
    previous = screen.get_clip()
    screen.set_clip(band)
    start = screen_w - offset
    if period > 0:
        while start > 0:
            start -= period
        while start < screen_w:
            screen.blit(text_surf, (start, y))
            start += period
    screen.set_clip(previous)
    return band

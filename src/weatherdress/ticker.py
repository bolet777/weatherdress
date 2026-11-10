"""Bandeau bas.

Désactivé tant que ``ticker.enabled`` n'est pas vrai. Sans phrase, la bande
reste vide. Une adresse de flux, lue ailleurs, peut remplacer la phrase fixe.
"""

import pygame

from . import fonts

SAMPLE_TEXT = (
    "●  Essai de bandeau  ●  Le texte défile de droite à gauche  ●  "
    "Météo, transport et agenda restent au-dessus  ●  "
)
DEFAULT_HEIGHT = 32
DEFAULT_SPEED = 48
LOOP_GAP = 28
# Bande sombre : le défilement reste lisible sans prendre le pas sur la scène.
BAND_BG = (16, 20, 28)
BAND_FG = (236, 232, 224)


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
    url = block.get("url")
    if not isinstance(url, str):
        url = ""
    try:
        minutes = int(block.get("refresh_minutes", 15))
    except (TypeError, ValueError):
        minutes = 15
    if minutes < 1:
        minutes = 15
    return {
        "height": height,
        "speed": speed,
        "text": text.strip(),
        "url": url.strip(),
        "refresh_minutes": minutes,
    }


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


def carry_offset(elapsed_s, speed_px_per_sec, period, text, state):
    """Comme `scroll_offset`, mais une nouvelle phrase reprend au pixel déjà atteint."""
    period = int(period)
    if period <= 0 or not text:
        return 0
    try:
        elapsed = float(elapsed_s)
        speed = float(speed_px_per_sec)
    except (TypeError, ValueError):
        return 0
    if elapsed < 0 or speed <= 0:
        return 0
    pixels = int(elapsed * speed)
    previous = state.get("text")
    old_period = int(state.get("period") or 0)
    bias = int(state.get("bias") or 0)
    if previous != text or old_period <= 0:
        if previous is not None and old_period > 0:
            old_offset = (pixels + bias) % old_period
            bias = (old_offset - (pixels % period)) % period
        else:
            bias = 0
        state["text"] = text
        state["period"] = period
        state["bias"] = bias
    elif old_period != period:
        old_offset = (pixels + bias) % old_period
        bias = (old_offset - (pixels % period)) % period
        state["period"] = period
        state["bias"] = bias
    return (pixels + bias) % period


_text_cache = {"key": None, "surface": None}
_scroll_state = {"text": None, "period": 0, "bias": 0}

TICKER_FPS = 30


def scrolling(config):
    """Vrai quand une phrase doit défiler. La boucle passe alors à TICKER_FPS."""
    spec = settings(config)
    return bool(spec and spec["text"])


_font_px_cache = {}


def band_font_px(band_h):
    """Plus grand corps SemiBold qui tient dans la bande, marges comprises."""
    band_h = int(band_h)
    cached = _font_px_cache.get(band_h)
    if cached is not None:
        return cached
    limit = max(8, band_h - 4)
    px = max(8, band_h)
    chosen = 8
    while px > 8:
        font = fonts.load(px, "semibold")
        if font.get_height() <= limit:
            chosen = px
            break
        px -= 1
    _font_px_cache[band_h] = chosen
    return chosen


def cached_text_surface(text, font_px):
    """La phrase n'est rendue qu'une fois. Seul le décalage change ensuite."""
    key = (text, int(font_px), BAND_FG, "semibold")
    if _text_cache["key"] != key:
        font = fonts.load(font_px, "semibold")
        _text_cache["surface"] = font.render(text, True, BAND_FG)
        _text_cache["key"] = key
    return _text_cache["surface"]


def cached_phrase():
    """Phrase déjà dessinée, ou une chaîne vide."""
    key = _text_cache["key"]
    if not key:
        return ""
    return key[0]


def paint(screen, config, elapsed_s, text=None):
    """Dessine le bandeau. Retourne son rectangle, ou None s'il est coupé.

    `text` remplace la phrase fixe quand un flux a fourni la sienne.
    """
    spec = settings(config)
    if spec is None:
        return None
    screen_w, screen_h = screen.get_size()
    band_h = spec["height"]
    band = pygame.Rect(0, max(0, screen_h - band_h), screen_w, min(band_h, screen_h))
    pygame.draw.rect(screen, BAND_BG, band)
    phrase = spec["text"] if text is None else text
    if not isinstance(phrase, str) or not phrase.strip():
        return band

    font_px = band_font_px(band_h)
    text_surf = cached_text_surface(phrase, font_px)
    period = text_surf.get_width() + LOOP_GAP
    offset = carry_offset(elapsed_s, spec["speed"], period, phrase, _scroll_state)
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

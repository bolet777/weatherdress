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
# Même verre que les cartes transport : display.TRANSIT_CARD_GLASS (148, 196, 240, 186).
GLASS_TOP = (186, 220, 250, 186)
GLASS_BOTTOM = (148, 196, 240, 186)
GLASS_EDGE = (255, 255, 255, 150)
GLASS_SHEEN = (255, 255, 255)
TEXT_COLOR = (32, 44, 62)
DOT_COLOR = (70, 88, 112, 255)
SEPARATOR = "●"
# Marge au-dessus des accents et sous les descendants, de chaque côté.
VERTICAL_SAFETY = 2
_PROBE = "ÉgÂjyqpçà"


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
_band_cache = {"key": None, "surface": None}
_dot_cache = {}
_scroll_state = {"text": None, "period": 0, "bias": 0}

TICKER_FPS = 30


def scrolling(config):
    """Vrai quand une phrase doit défiler. La boucle passe alors à TICKER_FPS."""
    spec = settings(config)
    return bool(spec and spec["text"])


_font_px_cache = {}


def _lerp(start, end, t):
    return tuple(int(round(start[i] + (end[i] - start[i]) * t)) for i in range(len(start)))


def _over(dst, src):
    """Pose une couleur RGBA sur une autre. Le verre et le reflet restent distincts."""
    sr, sg, sb, sa = src
    dr, dg, db, da = dst
    src_a = sa / 255
    dst_a = da / 255
    out_a = src_a + dst_a * (1 - src_a)
    if out_a <= 0:
        return (0, 0, 0, 0)
    out = []
    for channel, base in ((sr, dr), (sg, dg), (sb, db)):
        out.append((channel * src_a + base * dst_a * (1 - src_a)) / out_a)
    return tuple(int(round(channel)) for channel in (*out, out_a * 255))


def _render_band(width, height):
    """Dégradé, reflet et filet supérieur. Agrandi puis réduit pour adoucir le verre."""
    scale = 2
    big_w = max(1, width) * scale
    big_h = max(1, height) * scale
    surf = pygame.Surface((big_w, big_h), pygame.SRCALPHA)
    last = max(1, big_h - 1)
    for y in range(big_h):
        t = y / last
        color = _lerp(GLASS_TOP, GLASS_BOTTOM, t)
        if t < 0.42:
            fade = (1 - t / 0.42) ** 1.5
            color = _over(color, (*GLASS_SHEEN, int(round(24 * fade))))
        pygame.draw.line(surf, color, (0, y), (big_w, y))
    out = pygame.transform.smoothscale(surf, (max(1, width), max(1, height)))
    edge = pygame.Surface(out.get_size(), pygame.SRCALPHA)
    pygame.draw.line(edge, GLASS_EDGE, (0, 0), (out.get_width() - 1, 0), 1)
    out.blit(edge, (0, 0))
    return out


def cached_band_surface(width, height):
    """Le fond décoratif ne dépend que de la taille du bandeau."""
    key = (int(width), int(height))
    if _band_cache["key"] != key:
        _band_cache["surface"] = _render_band(*key)
        _band_cache["key"] = key
    return _band_cache["surface"]


def _rendered_height(font_px):
    font = fonts.load(font_px, "semibold")
    return font.render(_PROBE, True, TEXT_COLOR).get_height()


def band_font_px(band_h):
    """Plus grand corps dont accents et descendants tiennent, marge comprise."""
    band_h = int(band_h)
    cached = _font_px_cache.get(band_h)
    if cached is not None:
        return cached
    limit = max(8, band_h - 2 * VERTICAL_SAFETY)
    px = max(8, band_h)
    chosen = 8
    while px > 8:
        if _rendered_height(px) <= limit:
            chosen = px
            break
        px -= 1
    _font_px_cache[band_h] = chosen
    return chosen


def _separator_px(font_px):
    return max(4, min(8, int(round(font_px * 0.27))))


def _dot_surface(diameter):
    diameter = max(3, int(diameter))
    cached = _dot_cache.get(diameter)
    if cached is not None:
        return cached
    scale = 8
    size = diameter * scale
    big = pygame.Surface((size, size), pygame.SRCALPHA)
    pygame.draw.circle(big, DOT_COLOR, (size / 2, size / 2), size * 0.40)
    small = pygame.transform.smoothscale(big, (diameter, diameter))
    _dot_cache[diameter] = small
    return small


def _compose_phrase(text, font_px):
    """Textes et pastilles, chacun centré sur son rectangle de rendu."""
    font = fonts.load(int(font_px), "semibold")
    pieces = text.split(SEPARATOR)
    labels = [
        font.render(piece, True, TEXT_COLOR) if piece else None for piece in pieces
    ]
    dot = _dot_surface(_separator_px(font_px)) if len(pieces) > 1 else None
    height = font.get_height()
    for label in labels:
        if label is not None:
            height = max(height, label.get_height())
    if dot is not None:
        height = max(height, dot.get_height())
    width = 0
    for index, label in enumerate(labels):
        if label is not None:
            width += label.get_width()
        if dot is not None and index < len(labels) - 1:
            width += dot.get_width()
    strip = pygame.Surface((max(1, width), max(1, height)), pygame.SRCALPHA)
    x = 0
    for index, label in enumerate(labels):
        if label is not None:
            strip.blit(label, (x, (height - label.get_height()) // 2))
            x += label.get_width()
        if dot is not None and index < len(labels) - 1:
            strip.blit(dot, (x, (height - dot.get_height()) // 2))
            x += dot.get_width()
    return strip


def cached_text_surface(text, font_px):
    """La phrase n'est rendue qu'une fois. Seul le décalage change ensuite."""
    key = (text, int(font_px), TEXT_COLOR, "semibold", "glass")
    if _text_cache["key"] != key:
        _text_cache["surface"] = _compose_phrase(text, font_px)
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
    screen.blit(cached_band_surface(band.w, band.h), band.topleft)
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

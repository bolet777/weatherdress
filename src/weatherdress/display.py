import os
import textwrap
from datetime import datetime

import pygame

from . import ambient_background
from . import background_assets
from . import calendar_panel
from . import character_assets
from .badges import BADGE_AA_SCALE
from . import future_accessories_column
from . import layout_config
from . import ticker
from . import transit as transit_module
from . import weather_icons
from .paths import IMAGES_DIR


DEFAULT_BACKGROUND_COLOR = (255, 255, 255)
TEXT_ON_LIGHT_BG = (40, 40, 40)
TEXT_ON_DARK_BG = (245, 245, 245)
CIRCLE_BG_COLOR = (230, 230, 230)
CIRCLE_RADIUS = 210
CIRCLE_TOP_INSET = 14  # espace entre le bord haut de l’écran et le sommet du médaillon

TRANSIT_AFTER_WEATHER_GAP = 16
TRANSIT_CARD_HEIGHT = 80
TRANSIT_CARD_GAP = 11
TRANSIT_CARD_BORDER_RADIUS = 20
TRANSIT_CARD_TITLE_PX = 22
TRANSIT_CARD_SUBTITLE_PX = 16
TRANSIT_CARD_TIMES_PX = 24
TRANSIT_STRIP_MODE_LETTER_PX = 42
TRANSIT_GLASS_AA = 3
TRANSIT_BADGE_SIDE = 48
TRANSIT_BADGE_INSET = 14
TRANSIT_BADGE_GAP = 16
TRANSIT_BADGE_RADIUS = 12
TRANSIT_BADGE_BG = (47, 116, 242)
# Ancien nom du bandeau : le badge bus et métro partage cette couleur.
TRANSIT_CARD_STRIP_BUS = TRANSIT_BADGE_BG
TRANSIT_CARD_GLASS = (36, 52, 82, 220)
TRANSIT_CARD_BORDER = (214, 224, 242, 120)
TRANSIT_DIVIDER = (214, 224, 242, 150)
TRANSIT_TITLE = (255, 255, 255)
TRANSIT_SUBTITLE = (186, 196, 214)
TRANSIT_TIMES = (242, 164, 62)
TRANSIT_TIMES_PILL = (8, 16, 34, 168)
TRANSIT_PILL_SEP = (230, 236, 245, 170)

def _rgb_setting(config, key, default):
    """Lit une couleur RGB depuis config[key] : \"#rrggbb\" ou [R,G,B]. Sinon default."""
    raw = config.get(key)
    if isinstance(raw, str) and len(raw) == 7 and raw.startswith("#"):
        try:
            return tuple(int(raw[i : i + 2], 16) for i in (1, 3, 5))
        except ValueError:
            return default
    if isinstance(raw, (list, tuple)) and len(raw) == 3:
        return tuple(max(0, min(255, int(c))) for c in raw)
    return default


def background_color(config):
    """Couleur de fond depuis config (RGB 0–255). Défaut blanc si absent ou invalide."""
    return _rgb_setting(config, "background_color", DEFAULT_BACKGROUND_COLOR)


def circle_background_color(config):
    """Couleur du médaillon (cercle) depuis config. Même format que background_color."""
    return _rgb_setting(config, "circle_background_color", CIRCLE_BG_COLOR)


def _primary_text_color_for_rgb(rgb):
    """Texte lisible sur une couleur donnée (luminance BT.601, seuil 140)."""
    r, g, b = rgb
    luminance = 0.299 * r + 0.587 * g + 0.114 * b
    return TEXT_ON_DARK_BG if luminance < 140 else TEXT_ON_LIGHT_BG


def primary_text_color(config):
    """Texte lisible selon la luminance du fond principal (BT.601)."""
    return _primary_text_color_for_rgb(background_color(config))


def weather_background_alpha_255(config):
    """
    Opacité du fond météo plein écran : 0–1 (ex. 0.85) ou entier 0–255.
    1.0 / 255 = opaque ; 0 = invisible (seule la couleur `background_color` reste).
    """
    raw = config.get("weather_background_alpha", 1.0)
    try:
        a = float(raw)
    except (TypeError, ValueError):
        return 255
    if a > 1.0:
        return max(0, min(255, int(a)))
    a = max(0.0, min(1.0, a))
    return int(round(255 * a))


_IMAGE_CACHE = {}


def load_image(path):
    """Charge une image avec canal alpha. Retourne None si introuvable.

    Le fichier n'est relu qu'une fois : redessiner la scène ne bloque plus le bandeau.
    """
    if not path or not os.path.exists(path):
        return None
    cached = _IMAGE_CACHE.get(path)
    if cached is not None:
        return cached
    img = pygame.image.load(path).convert_alpha()
    _IMAGE_CACHE[path] = img
    return img


def fit_image(img, max_width, max_height):
    """Redimensionne proportionnellement pour tenir dans la boîte."""
    w, h = img.get_size()
    scale = min(max_width / w, max_height / h, 1.0)
    if scale < 1.0:
        img = pygame.transform.smoothscale(img, (int(w * scale), int(h * scale)))
    return img


def cover_image_to_size(img, target_w, target_h):
    """Agrandit l’image pour couvrir le rectangle, rogne le surplus au centre (type « cover »)."""
    iw, ih = img.get_size()
    if iw <= 0 or ih <= 0 or target_w <= 0 or target_h <= 0:
        s = pygame.Surface((max(1, target_w), max(1, target_h)), pygame.SRCALPHA)
        s.fill((0, 0, 0, 0))
        return s
    scale = max(target_w / iw, target_h / ih)
    nw, nh = max(1, int(iw * scale)), max(1, int(ih * scale))
    scaled = pygame.transform.smoothscale(img, (nw, nh))
    x = max(0, (nw - target_w) // 2)
    y = max(0, (nh - target_h) // 2)
    # Surface RGB opaque = fond noir par défaut : les PNG à alpha laissaient du noir au composite.
    out = pygame.Surface((target_w, target_h), pygame.SRCALPHA)
    out.fill((0, 0, 0, 0))
    out.blit(scaled, (0, 0), area=pygame.Rect(x, y, target_w, target_h))
    return out


_BG_MAP_STATE = {"path": None, "mtime": None, "data": None}
_BG_SCALED = {"path": None, "w": None, "h": None, "surf": None}


def _get_background_map_data(images_dir):
    """Charge `background_map.json` avec cache invalidé par mtime."""
    bg_dir = os.path.join(images_dir, "backgrounds")
    path = os.path.join(bg_dir, background_assets.MAP_FILENAME)
    if not os.path.isfile(path):
        return None
    mtime = os.path.getmtime(path)
    if _BG_MAP_STATE["path"] == path and _BG_MAP_STATE["mtime"] == mtime:
        return _BG_MAP_STATE["data"]
    data = background_assets.load_background_map(bg_dir)
    _BG_MAP_STATE["path"] = path
    _BG_MAP_STATE["mtime"] = mtime
    _BG_MAP_STATE["data"] = data
    return data


def _get_scaled_background_surface(images_dir, current_weather, screen_w, screen_h):
    """Surface plein écran du fond météo, ou None."""
    map_data = _get_background_map_data(images_dir)
    if not map_data:
        return None
    path = background_assets.resolve_background_image_path(
        images_dir, current_weather, map_data
    )
    if not path:
        return None
    if (
        _BG_SCALED["path"] == path
        and _BG_SCALED["w"] == screen_w
        and _BG_SCALED["h"] == screen_h
        and _BG_SCALED["surf"] is not None
    ):
        return _BG_SCALED["surf"]
    raw = load_image(path)
    if not raw:
        return None
    surf = cover_image_to_size(raw, screen_w, screen_h)
    _BG_SCALED["path"] = path
    _BG_SCALED["w"] = screen_w
    _BG_SCALED["h"] = screen_h
    _BG_SCALED["surf"] = surf
    return surf


def draw_aa_filled_circle(surface, center, radius, color):
    """Cercle plein aux bords lissés : dessin haute résolution puis smoothscale (comme draw_badge)."""
    if radius <= 0:
        return
    scale = BADGE_AA_SCALE
    dim = radius * 2 * scale
    hi = pygame.Surface((dim, dim), pygame.SRCALPHA)
    c = radius * scale
    pygame.draw.circle(hi, color, (c, c), radius * scale)
    circle_surf = pygame.transform.smoothscale(hi, (radius * 2, radius * 2))
    surface.blit(circle_surf, (center[0] - radius, center[1] - radius))


def apply_character_colorkey(surface, config):
    """
    Rend une couleur unique transparente (export PNG sans alpha mais fond uni).
    Attention : tout pixel de cette couleur disparaît (éviter si le personnage l’utilise).
    """
    raw = config.get("character_colorkey")
    if raw is None:
        return surface
    if isinstance(raw, (list, tuple)) and len(raw) == 3:
        rgb = tuple(max(0, min(255, int(c))) for c in raw)
        out = surface.copy()
        out.set_colorkey(rgb)
        return out
    return surface


def blit_centered_text_pill(
    surface,
    font,
    text,
    center_xy,
    padding=(14, 8),
    bg_rgba=(20, 22, 28, 200),
    fg=(248, 248, 248),
    border_radius=10,
):
    """Texte centré sur fond arrondi semi-transparent (lisible sur photo, rendu lissé)."""
    text_surf = font.render(text, True, fg)
    tw, th = text_surf.get_size()
    pw, ph = padding
    w, h = tw + 2 * pw, th + 2 * ph
    pill = pygame.Surface((w, h), pygame.SRCALPHA)
    pygame.draw.rect(pill, bg_rgba, pill.get_rect(), border_radius=border_radius)
    pill.blit(text_surf, (pw, ph))
    surface.blit(pill, pill.get_rect(center=center_xy))


def _weather_block_text_color(config, use_photo_background, use_circle):
    """Couleur du bloc météo : clair sur fond photo, sinon contraste avec médaillon ou fond."""
    if use_photo_background:
        return (255, 255, 255)
    if use_circle:
        return _primary_text_color_for_rgb(circle_background_color(config))
    return primary_text_color(config)


def _blit_text_right(
    surface, font, text, right_x, top_y, color, shadow=False
):
    """Dessine une ligne alignée à droite ; retourne la hauteur."""
    surf = font.render(text, True, color)
    rect = surf.get_rect()
    rect.right = right_x
    rect.top = top_y
    if shadow:
        sh = font.render(text, True, (30, 30, 35))
        for ox, oy in ((1, 1), (2, 2), (1, 2)):
            r2 = sh.get_rect()
            r2.right = right_x + ox
            r2.top = top_y + oy
            surface.blit(sh, r2)
    surface.blit(surf, rect)
    return rect.height


def _blit_text_left(
    surface, font, text, left_x, top_y, color, shadow=False
):
    """Dessine une ligne alignée à gauche ; retourne la hauteur."""
    surf = font.render(text, True, color)
    rect = surf.get_rect()
    rect.left = left_x
    rect.top = top_y
    if shadow:
        sh = font.render(text, True, (30, 30, 35))
        for ox, oy in ((1, 1), (2, 2), (1, 2)):
            r2 = sh.get_rect()
            r2.left = left_x + ox
            r2.top = top_y + oy
            surface.blit(sh, r2)
    surface.blit(surf, rect)
    return rect.height


def _font_size_clamped(layout, key_min, key_max, screen_h, fallback_frac):
    lo = int(layout[key_min])
    hi = int(layout[key_max])
    mid = max(lo, min(hi, int(screen_h * fallback_frac)))
    return mid


_weather_icon_source_cache = {}
_weather_icon_scaled_cache = {}

# Hauteur icône / hauteur du texte température (>1 = icône un peu au-dessus de la ligne)
WEATHER_ICON_HEIGHT_FACTOR = 1.5
# Dessin HR puis réduction pour limiter crénelures (cf. TIME_PILL_AA_SCALE)
WEATHER_ICON_AA_SCALE = 3


def _weather_icon_scaled_to_height(icon_path, height_px):
    """
    Adapte la hauteur du PNG à `height_px` (largeur proportionnelle).
    Réduction en deux passes smoothscale pour adoucir les bords.
    """
    h = max(1, int(round(height_px)))
    key = (icon_path, h, WEATHER_ICON_AA_SCALE)
    if key in _weather_icon_scaled_cache:
        return _weather_icon_scaled_cache[key]
    if icon_path not in _weather_icon_source_cache:
        _weather_icon_source_cache[icon_path] = pygame.image.load(
            icon_path
        ).convert_alpha()
    raw = _weather_icon_source_cache[icon_path]
    iw, ih_nat = raw.get_size()
    if ih_nat <= 0:
        nh = h
        nw = h
    else:
        nh = h
        nw = max(1, int(round(iw * nh / ih_nat)))
    aa = max(1, int(WEATHER_ICON_AA_SCALE))
    if aa <= 1:
        surf = pygame.transform.smoothscale(raw, (nw, nh))
    else:
        nh_hi = nh * aa
        nw_hi = max(1, int(round(iw * nh_hi / ih_nat)))
        hi_surf = pygame.transform.smoothscale(raw, (nw_hi, nh_hi))
        surf = pygame.transform.smoothscale(hi_surf, (nw, nh))
    _weather_icon_scaled_cache[key] = surf
    return surf


def _weather_icon_row_width(icon_path, base_text_height_px, icon_scale_h):
    """`icon_scale_h` = hauteur cible après facteur WEATHER_ICON_HEIGHT_FACTOR."""
    if not icon_path:
        return 0
    mh = base_text_height_px
    gap = max(5, int(round(mh * 0.14)))
    return gap + _weather_icon_scaled_to_height(icon_path, icon_scale_h).get_width()


def _blit_temperature_with_icon(
    surface,
    anchor,
    coord,
    top_y,
    temp_line,
    font,
    color,
    shadow,
    icon_path,
):
    """
    Température + icône sur une ligne, icône à droite du texte.
    anchor 'left' : coord = bord gauche du texte.
    anchor 'right' : coord = bord droit de l’icône (alignement global à droite).
    Retourne la hauteur de ligne utilisée sous le bloc (texte ± débord vertical de l’icône).
    """
    txt = font.render(temp_line, True, color)
    sh_surf = font.render(temp_line, True, (30, 30, 35)) if shadow else None
    mh = txt.get_height()
    icon_scale_h = max(1, int(round(mh * WEATHER_ICON_HEIGHT_FACTOR)))
    icon_surf = None
    if icon_path:
        try:
            icon_surf = _weather_icon_scaled_to_height(icon_path, icon_scale_h)
        except pygame.error:
            icon_surf = None
    gap = max(5, int(round(mh * 0.14))) if icon_surf else 0
    tw = txt.get_width()
    iw = icon_surf.get_width() if icon_surf else 0

    row_h = mh
    if anchor == "left":
        tx = coord
        if shadow and sh_surf is not None:
            for ox, oy in ((1, 1), (2, 2), (1, 2)):
                r2 = sh_surf.get_rect()
                r2.left = tx + ox
                r2.top = top_y + oy
                surface.blit(sh_surf, r2)
        rt = txt.get_rect()
        rt.left = tx
        rt.top = top_y
        surface.blit(txt, rt)
        if icon_surf is not None:
            iy = top_y + (mh - icon_surf.get_height()) // 2
            surface.blit(icon_surf, (tx + tw + gap, iy))
            row_h = max(row_h, ((mh - icon_surf.get_height()) // 2) + icon_surf.get_height())
        return row_h

    # anchor == "right": bord droit de l’icône à `coord`
    text_right_edge = coord - iw - gap
    if shadow and sh_surf is not None:
        for ox, oy in ((1, 1), (2, 2), (1, 2)):
            r2 = sh_surf.get_rect()
            r2.right = text_right_edge + ox
            r2.top = top_y + oy
            surface.blit(sh_surf, r2)
    rt = txt.get_rect()
    rt.right = text_right_edge
    rt.top = top_y
    surface.blit(txt, rt)
    if icon_surf is not None:
        iy = top_y + (mh - icon_surf.get_height()) // 2
        surface.blit(icon_surf, (coord - iw, iy))
        row_h = max(row_h, ((mh - icon_surf.get_height()) // 2) + icon_surf.get_height())
    return row_h


def transit_panel_reserved_height(config):
    """Le transport est dessiné sous le bloc météo ; plus de bandeau bas réservé."""
    return 0


def content_bottom_y(screen_h, reserved_px=0):
    """Dernière ligne de contenu : marge de 4 px, plus le bandeau s'il est réservé."""
    return int(screen_h) - 4 - max(0, int(reserved_px))


def _bottom_limit(screen_h, content_bottom):
    if content_bottom is None:
        return int(screen_h) - 4
    return int(content_bottom)


TIME_PILL_AA_SCALE = 3
TIME_PILL_TOP_MARGIN = 12
# Part de la hauteur d’écran visée pour la police. 0,15 × 480 = 72 px,
# taille dont le glyphe « 08:49 » occupe ~8 % de la hauteur (pilule de référence).
TIME_PILL_FONT_FRAC = 0.15
TIME_PILL_FG = (248, 248, 248)
TIME_PILL_BG_DEFAULT = (16, 39, 67, 242)


def _clamp_byte(value):
    return max(0, min(255, int(value)))


def _time_pill_bg(layout):
    """Fond de la pilule : [R, G, B] (opaque) ou [R, G, B, A]."""
    raw = layout.get("time_pill_bg") if isinstance(layout, dict) else None
    if isinstance(raw, (list, tuple)) and len(raw) in (3, 4):
        try:
            channels = [_clamp_byte(c) for c in raw]
        except (TypeError, ValueError):
            return TIME_PILL_BG_DEFAULT
        if len(channels) == 3:
            channels.append(255)
        return tuple(channels)
    return TIME_PILL_BG_DEFAULT


def _time_pill_layout(layout):
    merged = dict(layout_config.DEFAULT_LAYOUT)
    if isinstance(layout, dict):
        merged.update(layout)
    return merged


def _time_pill_metrics(screen_h, layout=None):
    """Tailles de la pilule horloge. La police suit l’écran entre min et max."""
    layout = _time_pill_layout(layout)
    h = max(240, int(screen_h))
    font_px = _font_size_clamped(
        layout, "time_font_min", "time_font_max", h, TIME_PILL_FONT_FRAC
    )
    font_px = max(12, font_px)
    # Marges serrées : le glyphe remplit la capsule, comme sur la pilule de référence.
    pad_y = max(6, int(round(font_px * 0.14)))
    pad_x = max(12, int(round(font_px * 0.39)))
    icon_r = max(10, int(round(font_px * 0.29)))
    gap = max(8, int(round(font_px * 0.28)))
    probe = pygame.font.SysFont("sans-serif", font_px, bold=False)
    text_h = probe.size("00:00")[1]
    pill_h = max(text_h + 2 * pad_y, 2 * pad_y + 2 * icon_r + 4)
    return {
        "font_px": font_px,
        "pad_x": pad_x,
        "pad_y": pad_y,
        "icon_r": icon_r,
        "gap": gap,
        "border_r": pill_h // 2,
        "pill_h": pill_h,
        "bg": _time_pill_bg(layout),
    }


def display_top_safe_margin(screen_h, layout=None):
    """Espace réservé sous le bord haut (pilule horloge + marge)."""
    m = _time_pill_metrics(screen_h, layout)
    return TIME_PILL_TOP_MARGIN + m["pill_h"] + 8


def _draw_simple_clock_icon(surface, center, radius, color, line_width):
    """Horloge en contour (cercle + aiguilles), pour rendu HR puis réduction."""
    cx, cy = center
    pygame.draw.circle(surface, color, (cx, cy), radius, line_width)
    pygame.draw.line(
        surface,
        color,
        (cx, cy),
        (cx, cy - max(4, int(radius * 0.67))),
        line_width,
    )
    pygame.draw.line(
        surface,
        color,
        (cx, cy),
        (cx + max(3, int(radius * 0.55)), cy + max(2, int(radius * 0.22))),
        line_width,
    )


def draw_time_pill(surface, screen_w, screen_h, layout=None):
    """Heure locale centrée en haut : dessin HR + smoothscale (bords lissés)."""
    s = TIME_PILL_AA_SCALE
    t_str = datetime.now().strftime("%H:%M")
    fg = TIME_PILL_FG
    m = _time_pill_metrics(screen_h, layout)
    bg = m["bg"]

    font_hi = pygame.font.SysFont("sans-serif", m["font_px"] * s, bold=False)
    text_surf = font_hi.render(t_str, True, fg)
    tw, th = text_surf.get_size()

    pad_x = m["pad_x"] * s
    pad_y = m["pad_y"] * s
    icon_r = m["icon_r"] * s
    gap = m["gap"] * s
    line_w = max(1, 2 * s)

    w_hi = 2 * pad_x + 2 * icon_r + gap + tw
    h_hi = max(th + 2 * pad_y, 2 * pad_y + 2 * icon_r + 4 * s)
    br = h_hi // 2

    pill_hi = pygame.Surface((w_hi, h_hi), pygame.SRCALPHA)
    pygame.draw.rect(pill_hi, bg, pill_hi.get_rect(), border_radius=br)

    cx = pad_x + icon_r
    cy = h_hi // 2
    _draw_simple_clock_icon(pill_hi, (cx, cy), icon_r, fg, line_w)

    text_x = pad_x + 2 * icon_r + gap
    pill_hi.blit(text_surf, (text_x, (h_hi - th) // 2))

    out_w = max(1, round(w_hi / s))
    out_h = max(1, round(h_hi / s))
    pill = pygame.transform.smoothscale(pill_hi, (out_w, out_h))
    surface.blit(
        pill, pill.get_rect(midtop=(screen_w // 2, TIME_PILL_TOP_MARGIN))
    )


def transit_panel_content_height(rows, row_stride):
    """Hauteur totale des cartes transport visibles."""
    n = len(rows)
    if n <= 0:
        return 0
    card_h = row_stride - TRANSIT_CARD_GAP
    return (n - 1) * row_stride + card_h


def transit_max_rows_from_start_y(screen_h, start_y, row_stride, content_bottom=None):
    """
    Nombre de cartes entières entre start_y et le bas utile.
    La dernière carte n’occupe que la hauteur de carte (pas un stride complet).
    """
    card_h = row_stride - TRANSIT_CARD_GAP
    avail = _bottom_limit(screen_h, content_bottom) - int(start_y)
    if avail < card_h:
        return 0
    return 1 + (avail - card_h) // row_stride


def resolve_transit_panel_start_y(
    char_rect, rows, row_stride, screen_h, content_bottom=None
):
    """
    Ancre le bas des cartes transport sur les pieds du personnage.
    Retourne None si aucune carte.
    """
    if not rows:
        return None
    panel_h = transit_panel_content_height(rows, row_stride)
    feet_y = min(int(char_rect.bottom), _bottom_limit(screen_h, content_bottom))
    return feet_y - panel_h


def plan_right_column_vertical_layout(
    char_rect,
    weather_total_h,
    transit_panel_h,
    screen_h,
    top_safe_px,
    vertical_offset_px=0,
    content_bottom=None,
):
    """
    Colonne droite (temp + desc + bus + métro) centrée verticalement sur le personnage.
    Retourne (weather_top_y, transit_start_y ou None).
    """
    gap = TRANSIT_AFTER_WEATHER_GAP if transit_panel_h > 0 else 0
    total = int(weather_total_h) + gap + int(transit_panel_h)
    top = int(round(char_rect.centery - total / 2.0)) + int(vertical_offset_px)
    max_top = _bottom_limit(screen_h, content_bottom) - total
    top = max(int(top_safe_px), min(top, max_top))
    weather_top = top
    transit_top = top + int(weather_total_h) + gap if transit_panel_h > 0 else None
    return weather_top, transit_top


def _weather_block_layout(
    config,
    current_weather,
    screen_w,
    screen_h,
    use_photo_background,
    use_circle,
    char_rect,
    layout,
):
    """Mesures et métadonnées du bloc météo (sans dessin)."""
    deg = "°C" if config.get("units", "metric") == "metric" else "°F"
    temp_line = f"{current_weather['temp']:.0f}{deg}"
    desc_raw = current_weather.get("description") or ""
    desc = desc_raw.strip()
    if desc:
        desc = desc[0].upper() + desc[1:] if len(desc) > 1 else desc.upper()

    color = _weather_block_text_color(config, use_photo_background, use_circle)
    use_shadow = use_photo_background

    margin_right = max(
        16, int(screen_w * float(layout["weather_screen_right_margin_pct"]))
    )
    right_x = screen_w - margin_right

    temp_size = _font_size_clamped(
        layout, "weather_temp_font_min", "weather_temp_font_max", screen_h, 0.22
    )
    desc_size = _font_size_clamped(
        layout, "weather_desc_font_min", "weather_desc_font_max", screen_h, 0.065
    )

    font_temp = pygame.font.SysFont("sans-serif", temp_size, bold=True)
    font_desc = pygame.font.SysFont("sans-serif", desc_size, bold=False)

    icon_path = weather_icons.get_weather_icon_path(
        IMAGES_DIR,
        current_weather.get("condition_id"),
        current_weather.get("icon"),
    )

    mode = layout.get("weather_mode", "after_character")
    if mode == "screen_right":
        wrap_cols = max(12, min(22, screen_w // 38))
        left_x = None
    else:
        gap_px = int(layout["weather_gap_after_character_px"])
        left_x = char_rect.right + gap_px
        left_x = max(0, min(left_x, screen_w - 72))
        avail_px = max(80, right_x - left_x)
        wrap_cols = max(8, min(28, avail_px // 9))

    desc_lines = textwrap.wrap(desc, width=wrap_cols) if desc else []
    if not desc_lines and desc:
        desc_lines = [desc]

    gap_td = 10
    line_gap = 6
    temp_line_h = font_temp.get_height()
    icon_target_h = max(1, int(round(temp_line_h * WEATHER_ICON_HEIGHT_FACTOR)))
    temp_h = max(temp_line_h, icon_target_h) if icon_path else temp_line_h
    if desc_lines:
        dh = font_desc.get_height()
        desc_block_h = len(desc_lines) * dh + max(0, len(desc_lines) - 1) * line_gap
    else:
        desc_block_h = 0
    weather_total_h = temp_h + gap_td + desc_block_h

    if mode == "screen_right":
        temp_text_w = font_temp.size(temp_line)[0]
        icon_extra = _weather_icon_row_width(
            icon_path, temp_line_h, icon_target_h
        )
        max_w = temp_text_w + icon_extra
        for ln in desc_lines:
            max_w = max(max_w, font_desc.size(ln)[0])
        column_left = right_x - max_w
    else:
        column_left = left_x

    return {
        "mode": mode,
        "temp_line": temp_line,
        "desc_lines": desc_lines,
        "font_temp": font_temp,
        "font_desc": font_desc,
        "color": color,
        "use_shadow": use_shadow,
        "icon_path": icon_path,
        "left_x": left_x,
        "right_x": right_x,
        "column_left": column_left,
        "gap_td": gap_td,
        "line_gap": line_gap,
        "weather_total_h": weather_total_h,
    }


def draw_weather_text_block(
    surface,
    config,
    current_weather,
    outfit,
    screen_w,
    screen_h,
    use_photo_background,
    use_circle,
    char_rect,
    layout,
    usable_screen_h=None,
    *,
    block_top_y=None,
    top_safe_px=None,
    weather_prep=None,
    content_bottom=None,
):
    """
    Température + description : position selon layout (après personnage ou bord droit).
    Retourne { "column_left", "bottom_y" } pour aligner le transport sur la même colonne.
    """
    uh = usable_screen_h if usable_screen_h is not None else screen_h
    prep = weather_prep or _weather_block_layout(
        config,
        current_weather,
        screen_w,
        screen_h,
        use_photo_background,
        use_circle,
        char_rect,
        layout,
    )
    mode = prep["mode"]
    temp_line = prep["temp_line"]
    desc_lines = prep["desc_lines"]
    font_temp = prep["font_temp"]
    font_desc = prep["font_desc"]
    color = prep["color"]
    use_shadow = prep["use_shadow"]
    icon_path = prep["icon_path"]
    left_x = prep["left_x"]
    right_x = prep["right_x"]
    column_left = prep["column_left"]
    gap_td = prep["gap_td"]
    line_gap = prep["line_gap"]
    total_h = prep["weather_total_h"]

    v_off = int(layout.get("weather_transit_vertical_offset_px", 0))
    top_safe = (
        int(top_safe_px)
        if top_safe_px is not None
        else display_top_safe_margin(screen_h, layout) + 4
    )

    limit = _bottom_limit(screen_h, content_bottom)
    if mode == "screen_right":
        y = max(int(uh * 0.14), (uh - total_h) // 2) + v_off
        y = max(top_safe, min(y, min(uh - total_h - 8, limit - total_h)))
        y += _blit_temperature_with_icon(
            surface,
            "right",
            right_x,
            y,
            temp_line,
            font_temp,
            color,
            use_shadow,
            icon_path,
        )
        y += gap_td
        for i, ln in enumerate(desc_lines):
            y += _blit_text_right(
                surface, font_desc, ln, right_x, y, color, shadow=use_shadow
            )
            if i < len(desc_lines) - 1:
                y += line_gap
        return {"column_left": column_left, "bottom_y": y}

    y = int(block_top_y)
    y = max(top_safe, min(y, limit - total_h))

    y += _blit_temperature_with_icon(
        surface,
        "left",
        left_x,
        y,
        temp_line,
        font_temp,
        color,
        use_shadow,
        icon_path,
    )
    y += gap_td
    for i, ln in enumerate(desc_lines):
        y += _blit_text_left(
            surface, font_desc, ln, left_x, y, color, shadow=use_shadow
        )
        if i < len(desc_lines) - 1:
            y += line_gap
    return {"column_left": column_left, "bottom_y": y}


def _place_character_rect(
    char_rect,
    *,
    char_center_x,
    char_y_fallback,
    screen_h,
    top_safe_margin,
    content_bottom=None,
):
    """Position verticale du sprite (centre par défaut, borné haut / bas utile)."""
    char_rect.centery = char_y_fallback
    if char_rect.top < top_safe_margin:
        char_rect.top = top_safe_margin
    limit = _bottom_limit(screen_h, content_bottom)
    if char_rect.bottom > limit:
        char_rect.bottom = limit


def _transit_font_px(raw, default, *, lo=8, hi=120):
    try:
        v = int(raw)
    except (TypeError, ValueError):
        return default
    return max(lo, min(hi, v))


def transit_card_layout(config):
    """
    Tailles de police et hauteur des cartes bus / métro (clés optionnelles sous ``transit``).
    """
    t = config.get("transit") if isinstance(config.get("transit"), dict) else {}
    title_px = _transit_font_px(
        t.get("card_title_font_px"), TRANSIT_CARD_TITLE_PX, lo=10, hi=48
    )
    subtitle_px = _transit_font_px(
        t.get("card_subtitle_font_px"), TRANSIT_CARD_SUBTITLE_PX, lo=8, hi=40
    )
    times_px = _transit_font_px(
        t.get("card_times_font_px"), TRANSIT_CARD_TIMES_PX, lo=10, hi=56
    )
    strip_letter_px = _transit_font_px(
        t.get("strip_mode_letter_font_px"), TRANSIT_STRIP_MODE_LETTER_PX, lo=12, hi=72
    )
    pad_inner = 12
    if t.get("card_height_px") is not None:
        card_h = _transit_font_px(
            t.get("card_height_px"), TRANSIT_CARD_HEIGHT, lo=48, hi=200
        )
    else:
        text_block = title_px + 3 + subtitle_px
        inner = max(text_block, times_px) + 2 * pad_inner
        card_h = max(TRANSIT_CARD_HEIGHT, inner)
    return {
        "title_px": title_px,
        "subtitle_px": subtitle_px,
        "times_px": times_px,
        "strip_letter_px": strip_letter_px,
        "card_height": card_h,
        "row_stride": card_h + TRANSIT_CARD_GAP,
    }


def transit_badge_metrics(host_w, host_h):
    """Côté du badge et largeur de gouttière (badge + filet) avant le texte."""
    room = int(host_h) - 2 * TRANSIT_BADGE_INSET
    side = max(28, min(TRANSIT_BADGE_SIDE, room))
    gutter = TRANSIT_BADGE_INSET + side + TRANSIT_BADGE_GAP
    cap = max(1, int(host_w) // 3)
    if gutter > cap:
        side = max(16, cap - TRANSIT_BADGE_INSET - TRANSIT_BADGE_GAP)
        gutter = cap
    return side, gutter


def transit_content_gutter(panel_w, panel_h):
    """Décalage du texte, identique sur une carte transport et sur l’agenda."""
    _side, gutter = transit_badge_metrics(panel_w, panel_h)
    return gutter


def transit_badge_rect(host):
    """Carré bleu centré verticalement dans la carte ou le panneau."""
    side, _gutter = transit_badge_metrics(host.w, host.h)
    return pygame.Rect(
        host.x + TRANSIT_BADGE_INSET,
        host.centery - side // 2,
        side,
        side,
    )


def _glass_local_rect(local, scale):
    return pygame.Rect(
        int(local.x * scale),
        int(local.y * scale),
        max(1, int(local.w * scale)),
        max(1, int(local.h * scale)),
    )


def _composite(big, draw):
    """Dessine sur un calque puis le fond, pour ne pas remplacer l’alpha du verre."""
    layer = pygame.Surface(big.get_size(), pygame.SRCALPHA)
    draw(layer)
    big.blit(layer, (0, 0))


def _glass_fill(big, scale, local, color, **radius_kwargs):
    scaled = {key: int(value * scale) for key, value in radius_kwargs.items()}
    area = _glass_local_rect(local, scale)

    def draw(layer):
        pygame.draw.rect(layer, color, area, **scaled)

    _composite(big, draw)


def _glass_line(big, scale, color, start, end):
    start_px = (int(start[0] * scale), int(start[1] * scale))
    end_px = (int(end[0] * scale), int(end[1] * scale))
    width = max(1, scale)

    def draw(layer):
        pygame.draw.line(layer, color, start_px, end_px, width)

    _composite(big, draw)


def paint_glass_card(screen, rect, draw_extra=None):
    """Carte verre : fond sombre translucide, liseré clair, coins arrondis."""
    rect = pygame.Rect(rect)
    if rect.w < 2 or rect.h < 2:
        return
    scale = TRANSIT_GLASS_AA
    big = pygame.Surface((rect.w * scale, rect.h * scale), pygame.SRCALPHA)
    radius = TRANSIT_CARD_BORDER_RADIUS * scale
    pygame.draw.rect(big, TRANSIT_CARD_GLASS, big.get_rect(), border_radius=radius)
    if draw_extra is not None:
        draw_extra(big, scale)
    stroke = max(1, scale)
    border = pygame.Rect(
        stroke // 2,
        stroke // 2,
        rect.w * scale - stroke,
        rect.h * scale - stroke,
    )

    def draw_border(layer):
        pygame.draw.rect(
            layer,
            TRANSIT_CARD_BORDER,
            border,
            width=stroke,
            border_radius=max(1, radius - stroke // 2),
        )

    _composite(big, draw_border)
    screen.blit(pygame.transform.smoothscale(big, (rect.w, rect.h)), rect.topleft)


def _draw_badge_divider(big, scale, badge_local):
    x = badge_local.right + TRANSIT_BADGE_GAP // 2
    _glass_line(
        big,
        scale,
        TRANSIT_DIVIDER,
        (x, badge_local.top + 8),
        (x, badge_local.bottom - 8),
    )


def _punch_round(surface, rect, radius):
    hole = pygame.Surface(surface.get_size(), pygame.SRCALPHA)
    pygame.draw.rect(hole, (255, 255, 255, 255), rect, border_radius=radius)
    surface.blit(hole, (0, 0), special_flags=pygame.BLEND_RGBA_SUB)


def _punch_circle(surface, center, radius):
    hole = pygame.Surface(surface.get_size(), pygame.SRCALPHA)
    pygame.draw.circle(hole, (255, 255, 255, 255), center, radius)
    surface.blit(hole, (0, 0), special_flags=pygame.BLEND_RGBA_SUB)


def _draw_bus_glyph(target, rect):
    """Bus emoji de face : aplat blanc, pare-brise et phares en creux."""
    white = (255, 255, 255, 255)
    mirror_w = max(2, rect.w // 11)
    body = pygame.Rect(
        rect.left + mirror_w,
        rect.top + int(rect.h * 0.04),
        rect.w - 2 * mirror_w,
        int(rect.h * 0.92),
    )
    roof = max(3, body.w // 3)
    base = max(2, body.w // 6)
    pygame.draw.rect(
        target,
        white,
        body,
        border_top_left_radius=roof,
        border_top_right_radius=roof,
        border_bottom_left_radius=base,
        border_bottom_right_radius=base,
    )
    mirror_h = max(3, body.h // 8)
    mirror_y = body.top + int(body.h * 0.30)
    for origin in (rect.left, body.right - 2):
        pygame.draw.rect(
            target,
            white,
            pygame.Rect(origin, mirror_y, mirror_w + 2, mirror_h),
            border_radius=mirror_h // 2,
        )
    windshield = pygame.Rect(
        body.left + int(body.w * 0.14),
        body.top + int(body.h * 0.16),
        int(body.w * 0.72),
        int(body.h * 0.32),
    )
    _punch_round(target, windshield, max(2, windshield.h // 3))
    light_r = max(2, body.w // 12)
    light_y = body.top + int(body.h * 0.70)
    for frac in (0.30, 0.70):
        _punch_circle(target, (body.left + int(body.w * frac), light_y), light_r)


def _draw_metro_glyph(target, rect):
    """Métro emoji de face : aplat blanc, vitres et phares en creux."""
    white = (255, 255, 255, 255)
    body = pygame.Rect(
        rect.left + int(rect.w * 0.16),
        rect.top + int(rect.h * 0.02),
        int(rect.w * 0.68),
        int(rect.h * 0.80),
    )
    nose = max(4, body.w // 3)
    pygame.draw.rect(target, white, body, border_radius=nose)
    sign = pygame.Rect(
        body.left + int(body.w * 0.24),
        body.top + int(body.h * 0.12),
        int(body.w * 0.52),
        max(2, int(body.h * 0.07)),
    )
    _punch_round(target, sign, max(1, sign.h // 2))
    win_w = max(2, int(body.w * 0.30))
    win_h = max(2, int(body.h * 0.30))
    win_y = body.top + int(body.h * 0.26)
    gap = max(2, int(body.w * 0.08))
    win_r = max(2, win_w // 6)
    for win_x in (body.centerx - gap // 2 - win_w, body.centerx + gap // 2):
        _punch_round(target, pygame.Rect(win_x, win_y, win_w, win_h), win_r)
    light_r = max(2, body.w // 13)
    light_y = body.top + int(body.h * 0.72)
    for frac in (0.30, 0.70):
        _punch_circle(target, (body.left + int(body.w * frac), light_y), light_r)
    rail_w = max(4, int(body.w * 0.46))
    rail_h = max(2, int(rect.h * 0.07))
    pygame.draw.rect(
        target,
        white,
        pygame.Rect(body.centerx - rail_w // 2, body.bottom, rail_w, rail_h),
        border_radius=max(1, rail_h // 2),
    )


def blit_mode_badge(screen, rect, kind):
    """Badge bleu et glyphe blanc (bus ou métro), bords lissés."""
    rect = pygame.Rect(rect)
    if rect.w < 8 or rect.h < 8:
        return
    scale = TRANSIT_GLASS_AA
    big = pygame.Surface((rect.w * scale, rect.h * scale), pygame.SRCALPHA)
    radius = min(TRANSIT_BADGE_RADIUS * scale, (min(rect.w, rect.h) * scale) // 2)
    pygame.draw.rect(
        big, (*TRANSIT_BADGE_BG, 255), big.get_rect(), border_radius=radius
    )
    pad = max(2, int(rect.w * scale * 0.12))
    inner = pygame.Rect(pad, pad, rect.w * scale - 2 * pad, rect.h * scale - 2 * pad)
    if kind in ("metro", "bus"):
        glyph = pygame.Surface(big.get_size(), pygame.SRCALPHA)
        if kind == "metro":
            _draw_metro_glyph(glyph, inner)
        else:
            _draw_bus_glyph(glyph, inner)
        big.blit(glyph, (0, 0))
    screen.blit(pygame.transform.smoothscale(big, (rect.w, rect.h)), rect.topleft)


def _transit_times_pill(times_px, minutes, times_color, max_h):
    """Capsule des prochains passages : « N min », séparées par un filet."""
    scale = TRANSIT_GLASS_AA
    font = pygame.font.SysFont("sans-serif", max(1, times_px * scale), bold=True)
    labels = [f"{minute} min" for minute in minutes] if minutes else ["—"]
    surfs = [font.render(label, True, times_color) for label in labels]
    gap = 11 * scale
    pad_x = 14 * scale
    pad_y = 7 * scale
    text_w = sum(surf.get_width() for surf in surfs)
    text_w += (gap * 2) * max(0, len(surfs) - 1)
    text_h = max(surf.get_height() for surf in surfs)
    pill_h = text_h + 2 * pad_y
    cap = max(text_h, int(max_h) * scale)
    if pill_h > cap:
        pill_h = cap
    pill_w = text_w + 2 * pad_x
    big = pygame.Surface((max(1, pill_w), max(1, pill_h)), pygame.SRCALPHA)
    pygame.draw.rect(
        big, TRANSIT_TIMES_PILL, big.get_rect(), border_radius=pill_h // 2
    )
    x = pad_x
    mid = pill_h // 2
    sep_half = max(4 * scale, pill_h // 5)
    for index, surf in enumerate(surfs):
        big.blit(surf, (x, mid - surf.get_height() // 2))
        x += surf.get_width()
        if index < len(surfs) - 1:
            x += gap
            pygame.draw.line(
                big,
                TRANSIT_PILL_SEP,
                (x, mid - sep_half),
                (x, mid + sep_half),
                max(1, scale),
            )
            x += gap
    out_w = max(1, round(pill_w / scale))
    out_h = max(1, round(pill_h / scale))
    return pygame.transform.smoothscale(big, (out_w, out_h))


def _metro_headsign_display_label(headsign_text: str) -> str:
    """
    Trip headsign GTFS / libellé mappé : parfois « Station Angrignon » alors que l’écran
    préfixe déjà par « Direction ». On retire uniquement le premier mot s’il est « station »
    (mot entier), pour éviter « Direction station … ».
    """
    t = (headsign_text or "").strip()
    if not t:
        return t
    parts = t.split()
    if parts and parts[0].lower() == "station":
        return " ".join(parts[1:]).strip()
    return t


def _transit_panel_build_rows(
    transit_data,
    config,
    *,
    screen_h,
    start_y,
    transit_phase_t=0.0,
    content_bottom=None,
):
    """
    Liste des cartes transport à afficher (même logique que draw_transit_panel).
    Chaque entrée : (mode, title, subtitle, minutes, strip_color).
    """
    transit_data = transit_data or {"bus": {}, "metro": {}}
    transit_config = config.get("transit", {}) or {}
    metro_color = tuple(
        transit_config.get("metro_line_color", [0, 70, 168])[:3]
    )
    metro_directions = transit_config.get("metro_directions", {}) or {}

    card_layout = transit_card_layout(config)
    row_stride = card_layout["row_stride"]
    max_rows = transit_max_rows_from_start_y(
        screen_h, start_y, row_stride, content_bottom=content_bottom
    )
    if max_rows < 1:
        return [], row_stride

    bus_rows: list[tuple] = []
    for sid, data in sorted(transit_data.get("bus", {}).items(), key=lambda x: x[0]):
        route = str(data.get("route", ""))
        title = f"Bus {route}".strip()
        subtitle = (data.get("label") or sid or "").strip()
        bus_rows.append(
            ("bus", title, subtitle, data.get("minutes") or [], TRANSIT_CARD_STRIP_BUS)
        )

    metro_station = (transit_config.get("metro_station") or "").strip()
    metro_rows: list[tuple] = []
    for headsign, minutes in sorted(transit_data.get("metro", {}).items()):
        direction = _metro_headsign_display_label(
            metro_directions.get(headsign, headsign) or ""
        )
        if metro_station:
            st = metro_station
            if st.lower().startswith("station"):
                title_m = st[0].upper() + st[1:] if st else st
            else:
                title_m = f"Station {st}"
            if direction.lower().startswith("direction"):
                subtitle_m = direction[0].upper() + direction[1:] if direction else direction
            else:
                subtitle_m = f"Direction {direction}" if direction else ""
        else:
            title_m = direction
            subtitle_m = ""
        metro_rows.append(
            ("metro", title_m, subtitle_m, minutes or [], metro_color)
        )

    try:
        period = float(transit_config.get("transit_alternate_seconds", 5) or 0)
    except (TypeError, ValueError):
        period = 5.0

    rows: list[tuple] = []
    if period > 0:
        phase = int(transit_phase_t // period)
        if bus_rows:
            rows.append(bus_rows[phase % len(bus_rows)])
        if metro_rows:
            rows.append(metro_rows[phase % len(metro_rows)])
    else:
        n_pairs = max(len(bus_rows), len(metro_rows))
        for i in range(n_pairs):
            if i < len(bus_rows):
                rows.append(bus_rows[i])
            if i < len(metro_rows):
                rows.append(metro_rows[i])
    return rows[:max_rows], row_stride


def transit_panel_last_visible_card_bottom(
    screen_h, start_y, rows, row_stride, content_bottom=None
):
    """Bas de la dernière carte réellement visible (même coupe que la boucle de dessin)."""
    card_h = row_stride - TRANSIT_CARD_GAP
    limit = _bottom_limit(screen_h, content_bottom)
    last_bottom = None
    for i, _ in enumerate(rows):
        card_y = int(start_y) + i * row_stride
        if card_y + card_h > limit:
            break
        last_bottom = card_y + card_h
    return last_bottom


def draw_transit_panel(
    screen,
    transit_data,
    config,
    *,
    column_left,
    start_y,
    margin_right,
    bg_surf,
    transit_phase_t=0.0,
    content_bottom=None,
):
    """
    transit_data : {"bus": {stop_id: {"route", "label", "minutes"}}, "metro": {headsign: [int, ...]}}
    Cartes verre : badge bleu, titre blanc, horaires dans une capsule.

    Si transit.transit_alternate_seconds > 0 (défaut 5), un seul arrêt bus et une seule
    direction métro à la fois, alternés toutes les N secondes (même phase). Si la clé
    vaut 0, entrelacement de toutes les lignes comme avant.
    """
    if not transit_module.transit_config_enabled(config):
        return
    screen_w, screen_h = screen.get_size()

    rows, row_stride = _transit_panel_build_rows(
        transit_data,
        config,
        screen_h=screen_h,
        start_y=start_y,
        transit_phase_t=transit_phase_t,
        content_bottom=content_bottom,
    )

    card_layout = transit_card_layout(config)
    card_h = card_layout["card_height"]

    right_x = screen_w - margin_right
    card_w = max(40, right_x - int(column_left))

    title_font = pygame.font.SysFont(
        "sans-serif", card_layout["title_px"], bold=True
    )
    sub_font = pygame.font.SysFont(
        "sans-serif", card_layout["subtitle_px"], bold=False
    )
    title_rgb = TRANSIT_TITLE
    sub_rgb = TRANSIT_SUBTITLE
    times_rgb = TRANSIT_TIMES
    pad_inner = 12

    for i, (mode, title, subtitle, minutes, _strip_color) in enumerate(rows):
        card_y = int(start_y) + i * row_stride
        if card_y + card_h > _bottom_limit(screen_h, content_bottom):
            break
        card_rect = pygame.Rect(int(column_left), card_y, card_w, card_h)
        badge = transit_badge_rect(card_rect)
        badge_local = badge.move(-card_rect.x, -card_rect.y)

        def _extra(big, scale, badge_local=badge_local):
            _draw_badge_divider(big, scale, badge_local)

        paint_glass_card(screen, card_rect, _extra)
        blit_mode_badge(screen, badge, "metro" if mode == "metro" else "bus")

        text_left = card_rect.x + transit_content_gutter(card_rect.w, card_rect.h)
        text_right = card_rect.right - pad_inner
        mid_y = card_rect.centery
        pill = _transit_times_pill(
            card_layout["times_px"], minutes, times_rgb, card_h - 16
        )
        pill_left = text_right - pill.get_width()
        text_clip = pygame.Rect(
            text_left,
            card_rect.y,
            max(1, pill_left - 10 - text_left),
            card_rect.h,
        )
        previous_clip = screen.get_clip()
        screen.set_clip(text_clip.clip(previous_clip))

        if subtitle and (mode == "bus" or subtitle != title):
            t_surf = title_font.render(title, True, title_rgb)
            s_surf = sub_font.render(subtitle, True, sub_rgb)
            block_h = t_surf.get_height() + 3 + s_surf.get_height()
            ty = mid_y - block_h // 2
            screen.blit(t_surf, (text_left, ty))
            screen.blit(s_surf, (text_left, ty + t_surf.get_height() + 3))
        else:
            t_surf = title_font.render(title, True, title_rgb)
            screen.blit(t_surf, (text_left, mid_y - t_surf.get_height() // 2))

        screen.set_clip(previous_clip)
        screen.blit(pill, (pill_left, mid_y - pill.get_height() // 2))


def render(
    screen,
    outfit,
    current_weather,
    images_dir,
    config,
    transit_data=None,
    *,
    transit_phase_t=0.0,
    calendar_events=None,
    calendar_phase_t=0.0,
    ticker_phase_t=0.0,
    shown_at=None,
    frame_metrics=None,
    present=True,
    paint_ticker=True,
):
    screen_w, screen_h = screen.get_size()
    band_h = ticker.band_height(config)
    bottom = content_bottom_y(screen_h, band_h)
    usable_h = max(120, screen_h - transit_panel_reserved_height(config) - band_h)

    bg_surf = None
    if config.get("use_weather_background", True):
        bg_surf = _get_scaled_background_surface(
            images_dir, current_weather, screen_w, screen_h
        )
        if bg_surf:
            # Sous les zones semi-transparentes du fond météo : couleur config, pas le buffer écran.
            ambient = ambient_background.resolve_ambient_background(
                current_weather, config
            )
            if ambient:
                fill_rgb, alpha = ambient
                screen.fill(fill_rgb)
            else:
                screen.fill(background_color(config))
                alpha = weather_background_alpha_255(config)
            if alpha < 255:
                faded = bg_surf.copy()
                faded.set_alpha(alpha)
                screen.blit(faded, (0, 0))
            else:
                screen.blit(bg_surf, (0, 0))
        else:
            screen.fill(background_color(config))
    else:
        screen.fill(background_color(config))

    layout = layout_config.effective_layout(config)
    draw_time_pill(screen, screen_w, screen_h, layout)

    use_photo_background = bg_surf is not None
    use_circle = not use_photo_background
    top_safe = display_top_safe_margin(screen_h, layout)

    # Médaillon : uniquement sans image météo plein écran (sinon personnage + texte sur le fond photo)
    if not use_photo_background:
        top_inset = max(0, min(CIRCLE_TOP_INSET, usable_h - 1))
        r_geom = (3 * (usable_h - top_inset) + 4) // 5  # ceil((3/5) * (usable_h - top_inset)) pour (5/3)r ≥ uh - top
        r = max(CIRCLE_RADIUS, r_geom)
        circle_cx = screen_w // 2
        circle_cy = top_inset + r
        draw_aa_filled_circle(
            screen, (circle_cx, circle_cy), r, circle_background_color(config)
        )

    chars_dir = os.path.join(images_dir, "characters")
    char_path = character_assets.resolve_character_png(chars_dir, outfit["character"])
    char_img_src = load_image(char_path) if char_path else None
    char_img = None

    char_center_x = int(screen_w * float(layout["character_center_x_pct"]))
    char_y_fallback = usable_h // 2 + int(layout["character_center_y_offset_px"])
    char_max_h = int(usable_h * float(layout["character_max_height_pct"]))
    char_max_w = int(screen_w * float(layout["character_max_width_pct"]))

    if char_img_src:
        char_img = fit_image(char_img_src, char_max_w, char_max_h)
        char_img = apply_character_colorkey(char_img, config)
        char_rect = char_img.get_rect()
        char_rect.centerx = char_center_x
        char_rect.centery = char_y_fallback
    else:
        char_rect = pygame.Rect(0, 0, 200, 350)
        char_rect.centerx = char_center_x
        char_rect.centery = char_y_fallback

    _place_character_rect(
        char_rect,
        char_center_x=char_center_x,
        char_y_fallback=char_y_fallback,
        screen_h=screen_h,
        top_safe_margin=top_safe,
        content_bottom=bottom,
    )

    margin_right = max(
        16, int(screen_w * float(layout["weather_screen_right_margin_pct"]))
    )

    weather_prep = _weather_block_layout(
        config,
        current_weather,
        screen_w,
        screen_h,
        use_photo_background,
        use_circle,
        char_rect,
        layout,
    )

    block_top_y = None
    transit_start_y = None
    transit_panel_h = 0
    transit_rows = []
    v_off = int(layout.get("weather_transit_vertical_offset_px", 0))
    top_safe_weather = top_safe + 4

    if layout.get("weather_mode", "after_character") == "after_character":
        transit_panel_h = 0
        transit_row_stride = transit_card_layout(config)["row_stride"]
        if transit_module.transit_config_enabled(config):
            transit_rows, transit_row_stride = _transit_panel_build_rows(
                transit_data,
                config,
                screen_h=screen_h,
                start_y=0,
                transit_phase_t=transit_phase_t,
                content_bottom=bottom,
            )
            transit_panel_h = transit_panel_content_height(
                transit_rows, transit_row_stride
            )
        block_top_y, transit_start_y = plan_right_column_vertical_layout(
            char_rect,
            weather_prep["weather_total_h"],
            transit_panel_h,
            screen_h,
            top_safe_weather,
            v_off,
            content_bottom=bottom,
        )
        if transit_start_y is not None:
            max_rows = transit_max_rows_from_start_y(
                screen_h,
                transit_start_y,
                transit_row_stride,
                content_bottom=bottom,
            )
            if max_rows < len(transit_rows):
                transit_rows = transit_rows[:max_rows]
                transit_panel_h = transit_panel_content_height(
                    transit_rows, transit_row_stride
                )
                block_top_y, transit_start_y = plan_right_column_vertical_layout(
                    char_rect,
                    weather_prep["weather_total_h"],
                    transit_panel_h,
                    screen_h,
                    top_safe_weather,
                    v_off,
                    content_bottom=bottom,
                )

    weather_layout = draw_weather_text_block(
        screen,
        config,
        current_weather,
        outfit,
        screen_w,
        screen_h,
        use_photo_background,
        use_circle,
        char_rect,
        layout,
        usable_screen_h=usable_h,
        block_top_y=block_top_y,
        top_safe_px=top_safe_weather,
        weather_prep=weather_prep,
        content_bottom=bottom,
    )

    if char_img:
        screen.blit(char_img, char_rect)
    else:
        if not use_photo_background:
            pygame.draw.rect(screen, (200, 200, 200), char_rect, border_radius=12)
        font = pygame.font.SysFont("sans-serif", 18)
        if use_photo_background:
            blit_centered_text_pill(
                screen,
                font,
                outfit["character"],
                char_rect.center,
                padding=(10, 6),
                border_radius=8,
            )
        else:
            label = font.render(outfit["character"], True, primary_text_color(config))
            screen.blit(label, label.get_rect(center=char_rect.center))

    future_accessories_column.draw_future_accessories_column(
        screen,
        outfit["current_accessories"],
        outfit["future_accessories"],
        char_rect,
        images_dir,
        config,
    )

    column_left = int(weather_layout["column_left"])
    card_w = max(40, screen_w - margin_right - column_left)
    transit_panel = None
    if transit_start_y is not None and transit_panel_h > 0:
        transit_panel = pygame.Rect(
            column_left, int(transit_start_y), card_w, int(transit_panel_h)
        )

    shown = shown_at if shown_at is not None else datetime.now().astimezone()
    agenda_column = layout.get("weather_mode", "after_character") == "after_character"
    calendar_on = calendar_panel.display_enabled(config, calendar_events)
    has_events = (
        calendar_panel.should_show_agenda(calendar_events, shown)
        if calendar_on
        else False
    )
    if agenda_column:
        side = calendar_panel.choose_side(
            calendar_enabled=calendar_on,
            transit_enabled=transit_panel is not None,
            has_events=has_events,
            rotate_seconds=calendar_panel.rotate_period(config),
            phase_t=calendar_phase_t,
        )
    else:
        side = "none"

    panel = transit_panel
    if side == "calendar":
        if panel is None:
            top = int(weather_layout["bottom_y"]) + TRANSIT_AFTER_WEATHER_GAP
            panel = pygame.Rect(
                column_left,
                top,
                card_w,
                max(0, bottom - top),
            )
        laid = calendar_panel.layout_agenda(calendar_events, shown, panel)
        if laid.show:
            calendar_panel.paint_agenda(screen, laid)
        elif transit_panel is not None:
            side = "transit"
            panel = transit_panel
    if side == "transit" and transit_panel is not None:
        draw_transit_panel(
            screen,
            transit_data,
            config,
            column_left=column_left,
            start_y=transit_panel.y,
            margin_right=margin_right,
            bg_surf=bg_surf,
            transit_phase_t=transit_phase_t,
            content_bottom=bottom,
        )
        panel = transit_panel

    if paint_ticker:
        ticker.paint(screen, config, ticker_phase_t)

    if frame_metrics is not None:
        frame_metrics.clear()
        frame_metrics.update(
            {
                "side": side,
                "weather_top": block_top_y,
                "weather_bottom": weather_layout["bottom_y"],
                "transit_top": None if transit_panel is None else transit_panel.y,
                "panel": panel,
                "column_left": column_left,
                "content_bottom": bottom,
                "ticker_band": band_h,
                "character_bottom": char_rect.bottom,
                "character_centerx": char_rect.centerx,
                "character_width": char_rect.width,
                "character_height": char_rect.height,
                "transit_row_count": len(transit_rows),
                "weather_temp_px": weather_prep["font_temp"].get_height(),
                "weather_desc_px": weather_prep["font_desc"].get_height(),
            }
        )

    if present:
        pygame.display.flip()


def render_status(screen, config, lines, *, present=True, paint_ticker=True):
    """Écran d’attente ou d’erreur (ex. clé API invalide) quand la météo n’est pas encore affichable."""
    screen_w, screen_h = screen.get_size()
    screen.fill(background_color(config))
    font = pygame.font.SysFont("sans-serif", 20)
    y = max(40, screen_h // 2 - len(lines) * 16)
    for line in lines:
        surf = font.render(line, True, primary_text_color(config))
        rect = surf.get_rect(center=(screen_w // 2, y))
        screen.blit(surf, rect)
        y += 32
    if paint_ticker:
        ticker.paint(screen, config, 0.0)
    if present:
        pygame.display.flip()

import os
import textwrap
from datetime import datetime

import pygame

from . import ambient_background
from . import background_assets
from . import character_assets
from . import i18n
from . import layout_config
from . import transit as transit_module
from . import weather_icons
from .paths import IMAGES_DIR


DEFAULT_BACKGROUND_COLOR = (255, 255, 255)
TEXT_ON_LIGHT_BG = (40, 40, 40)
TEXT_ON_DARK_BG = (245, 245, 245)
BADGE_BG_COLOR = (220, 50, 50)
BADGE_TEXT_COLOR = (255, 255, 255)
BADGE_AA_SCALE = 3  # sur-échantillonnage du cercle puis lissage (anti-crénelage)
FUTURE_ALPHA = 120  # transparence des accessoires futurs
CIRCLE_BG_COLOR = (230, 230, 230)
CIRCLE_RADIUS = 210
CIRCLE_TOP_INSET = 14  # espace entre le bord haut de l’écran et le sommet du médaillon

TRANSIT_AFTER_WEATHER_GAP = 16
TRANSIT_CARD_HEIGHT = 80
TRANSIT_CARD_GAP = 11
TRANSIT_STRIP_WIDTH = 58
TRANSIT_CARD_BORDER_RADIUS = 13
TRANSIT_CARD_TITLE_PX = 22
TRANSIT_CARD_SUBTITLE_PX = 16
TRANSIT_CARD_TIMES_PX = 24
TRANSIT_STRIP_ICON_PAD = 4
TRANSIT_STRIP_MODE_LETTER_PX = 42
TRANSIT_CARD_BG = (252, 253, 255)
TRANSIT_CARD_STRIP_BUS = (18, 52, 125)
TRANSIT_CARD_SHADOW_RGBA = (18, 24, 38, 58)
TRANSIT_CARD_SEP = (188, 194, 204)
# Texte sur la carte (fond clair)
TRANSIT_LABEL_ON_LIGHT = (34, 52, 102)
TRANSIT_TIMES_ON_LIGHT = (168, 82, 22)

ACCESSORY_BADGE_OFFSET = {
    "umbrella": (0.2, 0.8),
    "sunglasses": (0.5, 0.1),
    "hat": (0.5, 0.05),
    "boots": (0.7, 0.85),
    "scarf": (0.6, 0.4),
}


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


def load_image(path):
    """Charge une image avec canal alpha. Retourne None si introuvable."""
    if not os.path.exists(path):
        return None
    img = pygame.image.load(path).convert_alpha()
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


def draw_badge(surface, text, center):
    """Dessine une pastille ronde avec le texte centré."""
    font = pygame.font.SysFont("sans-serif", 14, bold=True)
    text_surf = font.render(text, True, BADGE_TEXT_COLOR)
    padding = 6
    radius = max(text_surf.get_width(), text_surf.get_height()) // 2 + padding

    scale = BADGE_AA_SCALE
    hi = pygame.Surface((radius * 2 * scale, radius * 2 * scale), pygame.SRCALPHA)
    c = radius * scale
    pygame.draw.circle(hi, BADGE_BG_COLOR, (c, c), radius * scale)
    badge_surf = pygame.transform.smoothscale(hi, (radius * 2, radius * 2))

    badge_surf.blit(
        text_surf,
        (radius - text_surf.get_width() // 2, radius - text_surf.get_height() // 2),
    )
    surface.blit(badge_surf, (center[0] - radius, center[1] - radius))


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


def _weather_forecast_line(future_note):
    """Extrait le texte des parenthèses pour une ligne sous la description (ex. prévisions)."""
    s = (future_note or "").strip()
    if not s:
        return ""
    if s.startswith("(") and s.endswith(")"):
        return s[1:-1].strip()
    return s


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


def _weather_icon_scaled_to_height(icon_path, height_px):
    """Adapte la hauteur du PNG à `height_px` (largeur proportionnelle), avec cache."""
    h = max(1, int(round(height_px)))
    key = (icon_path, h)
    if key in _weather_icon_scaled_cache:
        return _weather_icon_scaled_cache[key]
    if icon_path not in _weather_icon_source_cache:
        _weather_icon_source_cache[icon_path] = pygame.image.load(
            icon_path
        ).convert_alpha()
    raw = _weather_icon_source_cache[icon_path]
    iw, ih = raw.get_size()
    if ih <= 0:
        nh = h
        nw = h
    else:
        nh = h
        nw = max(1, int(round(iw * nh / ih)))
    surf = pygame.transform.smoothscale(raw, (nw, nh))
    _weather_icon_scaled_cache[key] = surf
    return surf


def _weather_icon_row_width(icon_path, text_height_px):
    if not icon_path:
        return 0
    gap = max(4, int(round(text_height_px * 0.12)))
    return gap + _weather_icon_scaled_to_height(icon_path, text_height_px).get_width()


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
    Retourne la hauteur de ligne (hauteur du rendu texte).
    """
    txt = font.render(temp_line, True, color)
    sh_surf = font.render(temp_line, True, (30, 30, 35)) if shadow else None
    mh = txt.get_height()
    icon_surf = None
    if icon_path:
        try:
            icon_surf = _weather_icon_scaled_to_height(icon_path, mh)
        except pygame.error:
            icon_surf = None
    gap = max(4, int(round(mh * 0.12))) if icon_surf else 0
    tw = txt.get_width()
    iw = icon_surf.get_width() if icon_surf else 0

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
            iy = top_y + max(0, (mh - icon_surf.get_height()) // 2)
            surface.blit(icon_surf, (tx + tw + gap, iy))
        return mh

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
        iy = top_y + max(0, (mh - icon_surf.get_height()) // 2)
        surface.blit(icon_surf, (coord - iw, iy))
    return mh


def transit_panel_reserved_height(config):
    """Le transport est dessiné sous le bloc météo ; plus de bandeau bas réservé."""
    return 0


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
):
    """
    Température + description : position selon layout (après personnage ou bord droit).
    Retourne { "column_left", "bottom_y" } pour aligner le transport sur la même colonne.
    """
    deg = "°C" if config.get("units", "metric") == "metric" else "°F"
    temp_line = f"{current_weather['temp']:.0f}{deg}"
    desc_raw = current_weather.get("description") or ""
    desc = desc_raw.strip()
    if desc:
        desc = desc[0].upper() + desc[1:] if len(desc) > 1 else desc.upper()

    future_note = i18n.format_weather_future_note(config, outfit["future_accessories"])
    forecast_line = _weather_forecast_line(future_note)

    color = _weather_block_text_color(config, use_photo_background, use_circle)
    use_shadow = use_photo_background
    uh = usable_screen_h if usable_screen_h is not None else screen_h

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
    note_size = _font_size_clamped(
        layout, "weather_note_font_min", "weather_note_font_max", screen_h, 0.048
    )

    font_temp = pygame.font.SysFont("sans-serif", temp_size, bold=True)
    font_desc = pygame.font.SysFont("sans-serif", desc_size, bold=False)
    font_note = pygame.font.SysFont("sans-serif", note_size, bold=False)

    icon_path = weather_icons.get_weather_icon_path(
        IMAGES_DIR,
        current_weather.get("condition_id"),
        current_weather.get("icon"),
    )

    mode = layout.get("weather_mode", "after_character")
    if mode == "screen_right":
        wrap_cols = max(12, min(22, screen_w // 38))
    else:
        gap_px = int(layout["weather_gap_after_character_px"])
        left_x = char_rect.right + gap_px
        left_x = max(0, min(left_x, screen_w - 72))
        avail_px = max(80, right_x - left_x)
        wrap_cols = max(8, min(28, avail_px // 9))

    desc_lines = textwrap.wrap(desc, width=wrap_cols) if desc else []
    if not desc_lines and desc:
        desc_lines = [desc]

    gap_td = 8
    line_gap = 4
    temp_h = font_temp.get_height()
    if desc_lines:
        dh = font_desc.get_height()
        desc_block_h = len(desc_lines) * dh + max(0, len(desc_lines) - 1) * line_gap
    else:
        desc_block_h = 0
    note_h = (4 + font_note.get_height()) if forecast_line else 0
    total_h = temp_h + gap_td + desc_block_h + note_h

    if mode == "screen_right":
        temp_text_w = font_temp.size(temp_line)[0]
        icon_extra = _weather_icon_row_width(icon_path, temp_h)
        max_w = temp_text_w + icon_extra
        for ln in desc_lines:
            max_w = max(max_w, font_desc.size(ln)[0])
        if forecast_line:
            max_w = max(max_w, font_note.size(forecast_line)[0])
        column_left = right_x - max_w

        y = max(int(uh * 0.14), (uh - total_h) // 2)
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
        if forecast_line:
            y += 4
            y += _blit_text_right(
                surface, font_note, forecast_line, right_x, y, color, shadow=use_shadow
            )
        return {"column_left": column_left, "bottom_y": y}

    gap_px = int(layout["weather_gap_after_character_px"])
    left_x = char_rect.right + gap_px
    left_x = max(0, min(left_x, screen_w - 72))
    y = int(float(layout["weather_top_pct"]) * uh)
    y = max(4, min(y, uh - total_h - 8))

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
    if forecast_line:
        y += 4
        y += _blit_text_left(
            surface, font_note, forecast_line, left_x, y, color, shadow=use_shadow
        )
    return {"column_left": left_x, "bottom_y": y}


TIME_PILL_AA_SCALE = 3
TIME_PILL_FONT_PX = 28
TIME_PILL_ICON_R = 12
TIME_PILL_GAP = 10
TIME_PILL_PAD_X = 18
TIME_PILL_PAD_Y = 11
TIME_PILL_BORDER_R = 12


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


def draw_time_pill(surface, screen_w, top_margin=12):
    """Heure locale centrée en haut : dessin HR + smoothscale (bords lissés)."""
    s = TIME_PILL_AA_SCALE
    t_str = datetime.now().strftime("%H:%M")
    fg = (248, 248, 248)
    bg = (20, 22, 28, 200)

    font_hi = pygame.font.SysFont("sans-serif", TIME_PILL_FONT_PX * s, bold=False)
    text_surf = font_hi.render(t_str, True, fg)
    tw, th = text_surf.get_size()

    pad_x = TIME_PILL_PAD_X * s
    pad_y = TIME_PILL_PAD_Y * s
    icon_r = TIME_PILL_ICON_R * s
    gap = TIME_PILL_GAP * s
    br = TIME_PILL_BORDER_R * s
    line_w = max(1, 2 * s)

    w_hi = 2 * pad_x + 2 * icon_r + gap + tw
    h_hi = max(th + 2 * pad_y, 2 * pad_y + 2 * icon_r + 4 * s)

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
    surface.blit(pill, pill.get_rect(midtop=(screen_w // 2, top_margin)))


def _transit_blit_card_shadow(screen, rect, br):
    sh = pygame.Surface((rect.w, rect.h), pygame.SRCALPHA)
    pygame.draw.rect(sh, TRANSIT_CARD_SHADOW_RGBA, sh.get_rect(), border_radius=br)
    screen.blit(sh, (rect.x + 3, rect.y + 4))


def _transit_strip_mode_letter(screen, strip_rect, letter):
    """Repli : lettre centrée si les PNG d’icônes manquent."""
    x, y, w, h = strip_rect
    cx, cy = x + w // 2, y + h // 2
    font = pygame.font.SysFont("sans-serif", TRANSIT_STRIP_MODE_LETTER_PX, bold=True)
    surf = font.render(letter, True, (255, 255, 255))
    screen.blit(surf, surf.get_rect(center=(cx, cy)))


def _transit_blit_strip_icon(screen, strip_rect, icon_filename):
    """
    Icône centrée dans le bandeau, même taille que la cartouche (pas d’élargissement).
    """
    path = os.path.join(IMAGES_DIR, "icons", icon_filename)
    img = load_image(path)
    if not img:
        return False
    pad = TRANSIT_STRIP_ICON_PAD
    mw = max(1, strip_rect.width - 2 * pad)
    mh = max(1, strip_rect.height - 2 * pad)
    scaled = fit_image(img, mw, mh)
    screen.blit(scaled, scaled.get_rect(center=strip_rect.center))
    return True


def _transit_strip_bus(screen, strip_rect):
    if not _transit_blit_strip_icon(screen, strip_rect, "bus.png"):
        _transit_strip_mode_letter(screen, strip_rect, "B")


def _transit_strip_metro(screen, strip_rect):
    if not _transit_blit_strip_icon(screen, strip_rect, "subway.png"):
        _transit_strip_mode_letter(screen, strip_rect, "M")


def _transit_blit_times_row(
    screen, font, minutes, times_color, sep_rgb, content_right, mid_y
):
    """Affiche 0–2 cellules « Nmin » avec séparateurs verticaux, alignées à droite."""
    if not minutes:
        dash = font.render("—", True, times_color)
        screen.blit(dash, dash.get_rect(midright=(content_right, mid_y)))
        return
    surfs = [font.render(f"{m}min", True, times_color) for m in minutes]
    sep_half_h = 16
    gap = 10
    total_w = sum(s.get_width() for s in surfs) + gap * 2 * max(0, len(surfs) - 1)
    x = content_right - total_w
    for i, s in enumerate(surfs):
        screen.blit(s, (x, mid_y - s.get_height() // 2))
        x += s.get_width()
        if i < len(surfs) - 1:
            x += gap
            pygame.draw.line(
                screen,
                sep_rgb,
                (x, mid_y - sep_half_h),
                (x, mid_y + sep_half_h),
                1,
            )
            x += gap


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
):
    """
    transit_data : {"bus": {stop_id: {"route", "label", "minutes"}}, "metro": {headsign: [int, ...]}}
    Cartes blanches (bandeau mode + texte + horaires), style tableau d’arrêt.

    Si transit.transit_alternate_seconds > 0 (défaut 5), un seul arrêt bus et une seule
    direction métro à la fois, alternés toutes les N secondes (même phase). Si la clé
    vaut 0, entrelacement de toutes les lignes comme avant.
    """
    if not transit_module.transit_config_enabled(config):
        return
    transit_data = transit_data or {"bus": {}, "metro": {}}
    screen_w, screen_h = screen.get_size()
    transit_config = config.get("transit", {}) or {}
    metro_color = tuple(
        transit_config.get("metro_line_color", [0, 70, 168])[:3]
    )
    metro_directions = transit_config.get("metro_directions", {}) or {}

    right_x = screen_w - margin_right
    card_w = max(40, right_x - int(column_left))
    br = TRANSIT_CARD_BORDER_RADIUS
    strip_w = min(TRANSIT_STRIP_WIDTH, card_w // 3)
    row_stride = TRANSIT_CARD_HEIGHT + TRANSIT_CARD_GAP
    max_rows = max(1, (screen_h - 8 - int(start_y)) // row_stride)

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
    rows = rows[:max_rows]

    title_font = pygame.font.SysFont("sans-serif", TRANSIT_CARD_TITLE_PX, bold=True)
    sub_font = pygame.font.SysFont("sans-serif", TRANSIT_CARD_SUBTITLE_PX, bold=False)
    times_font = pygame.font.SysFont("sans-serif", TRANSIT_CARD_TIMES_PX, bold=True)
    title_rgb = TRANSIT_LABEL_ON_LIGHT
    sub_rgb = TRANSIT_LABEL_ON_LIGHT
    times_rgb = TRANSIT_TIMES_ON_LIGHT

    pad_inner = 12
    content_left_off = strip_w + pad_inner

    for i, (mode, title, subtitle, minutes, strip_color) in enumerate(rows):
        card_y = int(start_y) + i * row_stride
        if card_y + TRANSIT_CARD_HEIGHT > screen_h - 4:
            break
        card_rect = pygame.Rect(int(column_left), card_y, card_w, TRANSIT_CARD_HEIGHT)
        _transit_blit_card_shadow(screen, card_rect, br)
        pygame.draw.rect(screen, TRANSIT_CARD_BG, card_rect, border_radius=br)

        strip_rect = pygame.Rect(card_rect.x, card_rect.y, strip_w, card_rect.h)
        pygame.draw.rect(
            screen,
            strip_color,
            strip_rect,
            border_top_left_radius=br,
            border_top_right_radius=0,
            border_bottom_left_radius=br,
            border_bottom_right_radius=0,
        )
        if mode == "bus":
            _transit_strip_bus(screen, strip_rect)
        else:
            _transit_strip_metro(screen, strip_rect)

        text_left = card_rect.x + content_left_off
        text_right = card_rect.right - pad_inner
        mid_y = card_rect.centery

        if mode == "bus" and subtitle:
            t_surf = title_font.render(title, True, title_rgb)
            s_surf = sub_font.render(subtitle, True, sub_rgb)
            block_h = t_surf.get_height() + 3 + s_surf.get_height()
            ty = mid_y - block_h // 2
            screen.blit(t_surf, (text_left, ty))
            screen.blit(s_surf, (text_left, ty + t_surf.get_height() + 3))
        elif mode == "metro" and subtitle and subtitle != title:
            t_surf = title_font.render(title, True, title_rgb)
            s_surf = sub_font.render(subtitle, True, sub_rgb)
            block_h = t_surf.get_height() + 3 + s_surf.get_height()
            ty = mid_y - block_h // 2
            screen.blit(t_surf, (text_left, ty))
            screen.blit(s_surf, (text_left, ty + t_surf.get_height() + 3))
        else:
            t_surf = title_font.render(title, True, title_rgb)
            screen.blit(t_surf, (text_left, mid_y - t_surf.get_height() // 2))

        times_area_right = text_right
        _transit_blit_times_row(
            screen,
            times_font,
            minutes,
            times_rgb,
            TRANSIT_CARD_SEP,
            times_area_right,
            mid_y,
        )


def render(
    screen,
    outfit,
    current_weather,
    images_dir,
    config,
    transit_data=None,
    *,
    transit_phase_t=0.0,
):
    screen_w = config["screen_width"]
    screen_h = config["screen_height"]
    usable_h = max(120, screen_h - transit_panel_reserved_height(config))

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

    use_photo_background = bg_surf is not None
    use_circle = not use_photo_background

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
    char_img = load_image(char_path) if char_path else None

    layout = layout_config.effective_layout(config)
    char_center_x = int(screen_w * float(layout["character_center_x_pct"]))
    char_y = usable_h // 2 + int(layout["character_center_y_offset_px"])
    char_max_h = int(usable_h * float(layout["character_max_height_pct"]))
    char_max_w = int(screen_w * float(layout["character_max_width_pct"]))

    if char_img:
        char_img = fit_image(char_img, char_max_w, char_max_h)
        char_img = apply_character_colorkey(char_img, config)
        char_rect = char_img.get_rect(center=(char_center_x, char_y))
        screen.blit(char_img, char_rect)
    else:
        # Placeholder si l'image est manquante
        char_rect = pygame.Rect(0, 0, 200, 350)
        char_rect.center = (char_center_x, char_y)
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

    acc_dir = os.path.join(images_dir, "accessories")

    # Accessoires actuels — normaux
    for acc_name in outfit["current_accessories"]:
        acc_img = load_image(os.path.join(acc_dir, f"{acc_name}.png"))
        if acc_img:
            acc_img = fit_image(acc_img, char_rect.width, char_rect.height)
            acc_img = apply_character_colorkey(acc_img, config)
            screen.blit(acc_img, char_rect)

    # Accessoires futurs — semi-transparents + pastille
    for item in outfit["future_accessories"]:
        acc_img = load_image(os.path.join(acc_dir, f"{item['accessory']}.png"))
        if acc_img:
            acc_img = fit_image(acc_img, char_rect.width, char_rect.height)
            acc_img = apply_character_colorkey(acc_img, config)
            # Appliquer l'alpha sur une copie
            ghost = acc_img.copy()
            ghost.set_alpha(FUTURE_ALPHA)
            screen.blit(ghost, char_rect)
            badge_text = f"{item['hour']}H"
            offset = ACCESSORY_BADGE_OFFSET.get(item["accessory"], (0.8, 0.2))
            badge_center = (
                char_rect.left + int(char_rect.width * offset[0]),
                char_rect.top + int(char_rect.height * offset[1]),
            )
            draw_badge(screen, badge_text, badge_center)

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
    )

    if transit_module.transit_config_enabled(config):
        margin_right = max(
            16, int(screen_w * float(layout["weather_screen_right_margin_pct"]))
        )
        draw_transit_panel(
            screen,
            transit_data,
            config,
            column_left=weather_layout["column_left"],
            start_y=weather_layout["bottom_y"] + TRANSIT_AFTER_WEATHER_GAP,
            margin_right=margin_right,
            bg_surf=bg_surf,
            transit_phase_t=transit_phase_t,
        )

    draw_time_pill(screen, screen_w)

    pygame.display.flip()


def render_status(screen, config, lines):
    """Écran d’attente ou d’erreur (ex. clé API invalide) quand la météo n’est pas encore affichable."""
    screen_w = config["screen_width"]
    screen_h = config["screen_height"]
    screen.fill(background_color(config))
    font = pygame.font.SysFont("sans-serif", 20)
    y = max(40, screen_h // 2 - len(lines) * 16)
    for line in lines:
        surf = font.render(line, True, primary_text_color(config))
        rect = surf.get_rect(center=(screen_w // 2, y))
        screen.blit(surf, rect)
        y += 32
    pygame.display.flip()

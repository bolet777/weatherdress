import os
import textwrap

import pygame

from . import background_assets
from . import character_assets
from . import i18n
from . import layout_config
from . import transit as transit_module


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

TRANSIT_PANEL_HEIGHT = 130  # bandeau bas (bus + métro) ; réserver la même hauteur au layout principal

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


def transit_panel_reserved_height(config):
    """Pixels réservés en bas lorsque la section `transit` est activée dans config."""
    return TRANSIT_PANEL_HEIGHT if transit_module.transit_config_enabled(config) else 0


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
    """Température + description : position selon layout (après personnage ou bord droit)."""
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
        y = max(int(uh * 0.14), (uh - total_h) // 2)
        y += _blit_text_right(
            surface, font_temp, temp_line, right_x, y, color, shadow=use_shadow
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
            _blit_text_right(
                surface, font_note, forecast_line, right_x, y, color, shadow=use_shadow
            )
        return

    gap_px = int(layout["weather_gap_after_character_px"])
    left_x = char_rect.right + gap_px
    left_x = max(0, min(left_x, screen_w - 72))
    y = int(float(layout["weather_top_pct"]) * uh)
    y = max(4, min(y, uh - total_h - 8))

    y += _blit_text_left(
        surface, font_temp, temp_line, left_x, y, color, shadow=use_shadow
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
        _blit_text_left(
            surface, font_note, forecast_line, left_x, y, color, shadow=use_shadow
        )


def draw_transit_panel(screen, transit_data, config):
    """
    transit_data : {"bus": {stop_id: {"route", "label", "minutes"}}, "metro": {headsign: [int, ...]}}
    """
    if not transit_module.transit_config_enabled(config):
        return
    transit_data = transit_data or {"bus": {}, "metro": {}}
    screen_w, screen_h = screen.get_size()
    panel_y = screen_h - TRANSIT_PANEL_HEIGHT
    transit_config = config.get("transit", {}) or {}
    metro_color = tuple(
        transit_config.get("metro_line_color", [0, 70, 168])[:3]
    )
    metro_directions = transit_config.get("metro_directions", {}) or {}

    panel_surf = pygame.Surface((screen_w, TRANSIT_PANEL_HEIGHT), pygame.SRCALPHA)
    panel_surf.fill((0, 0, 0, 180))
    screen.blit(panel_surf, (0, panel_y))

    font_label = pygame.font.SysFont("sans-serif", 17, bold=True)
    font_times = pygame.font.SysFont("sans-serif", 17)

    row_height = 28
    padding_x = 14
    padding_y = 6
    max_rows = max(1, (TRANSIT_PANEL_HEIGHT - 2 * padding_y) // row_height)

    rows = []
    for sid, data in sorted(transit_data.get("bus", {}).items(), key=lambda x: x[0]):
        label = f"Bus {data['route']} {data['label']}"
        rows.append(("bus", label, data.get("minutes") or [], None))

    for headsign, minutes in sorted(transit_data.get("metro", {}).items()):
        display_name = metro_directions.get(headsign, headsign)
        rows.append(("metro", display_name, minutes or [], metro_color))

    rows = rows[:max_rows]

    for i, (mode, label, minutes, color) in enumerate(rows):
        y = panel_y + padding_y + i * row_height

        icon_rect = pygame.Rect(padding_x, y + 2, 40, 22)
        if mode == "bus":
            pygame.draw.rect(screen, (60, 120, 200), icon_rect, border_radius=4)
            icon_text = font_label.render("BUS", True, (255, 255, 255))
        else:
            pygame.draw.ellipse(screen, color, icon_rect)
            icon_text = font_label.render("M", True, (255, 255, 255))
        screen.blit(icon_text, icon_text.get_rect(center=icon_rect.center))

        label_surf = font_label.render(label, True, (220, 220, 220))
        screen.blit(label_surf, (padding_x + 48, y + 2))

        if minutes:
            times_str = "  ".join(f"{m}mn" for m in minutes)
        else:
            times_str = "—"
        times_surf = font_times.render(times_str, True, (255, 220, 80))
        screen.blit(times_surf, (screen_w - times_surf.get_width() - padding_x, y + 2))


def render(screen, outfit, current_weather, images_dir, config, transit_data=None):
    screen_w = config["screen_width"]
    screen_h = config["screen_height"]
    reserved_bottom = transit_panel_reserved_height(config)
    usable_h = max(120, screen_h - reserved_bottom)

    bg_surf = None
    if config.get("use_weather_background", True):
        bg_surf = _get_scaled_background_surface(
            images_dir, current_weather, screen_w, screen_h
        )
        if bg_surf:
            # Sous les zones semi-transparentes du fond météo : couleur config, pas le buffer écran.
            screen.fill(background_color(config))
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

    draw_weather_text_block(
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

    draw_transit_panel(screen, transit_data, config)

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

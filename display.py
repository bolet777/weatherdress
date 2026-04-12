import os
import pygame

import i18n
import character_assets


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


def render(screen, outfit, current_weather, images_dir, config):
    screen_w = config["screen_width"]
    screen_h = config["screen_height"]

    screen.fill(background_color(config))

    # Médaillon : léger écart en haut ; bas coupé d’au moins 1/6 du diamètre (soit ≥ r/3 sous l’écran)
    top_inset = max(0, min(CIRCLE_TOP_INSET, screen_h - 1))
    r_geom = (3 * (screen_h - top_inset) + 4) // 5  # ceil((3/5) * (screen_h - top_inset)) pour (5/3)r ≥ sh - top
    r = max(CIRCLE_RADIUS, r_geom)
    circle_cx = screen_w // 2
    circle_cy = top_inset + r
    draw_aa_filled_circle(screen, (circle_cx, circle_cy), r, circle_background_color(config))

    chars_dir = os.path.join(images_dir, "characters")
    char_path = character_assets.resolve_character_png(chars_dir, outfit["character"])
    char_img = load_image(char_path) if char_path else None

    # Zone du personnage : 70% de la hauteur, centré
    char_max_h = int(screen_h * 0.80)
    char_max_w = int(screen_w * 0.60)

    if char_img:
        char_img = fit_image(char_img, char_max_w, char_max_h)
        char_rect = char_img.get_rect(center=(screen_w // 2, screen_h // 2 - 20))
        screen.blit(char_img, char_rect)
    else:
        # Placeholder si l'image est manquante
        char_rect = pygame.Rect(0, 0, 200, 350)
        char_rect.center = (screen_w // 2, screen_h // 2 - 20)
        pygame.draw.rect(screen, (200, 200, 200), char_rect, border_radius=12)
        font = pygame.font.SysFont("sans-serif", 18)
        label = font.render(outfit["character"], True, primary_text_color(config))
        screen.blit(label, label.get_rect(center=char_rect.center))

    acc_dir = os.path.join(images_dir, "accessories")

    # Accessoires actuels — normaux
    for acc_name in outfit["current_accessories"]:
        acc_img = load_image(os.path.join(acc_dir, f"{acc_name}.png"))
        if acc_img:
            acc_img = fit_image(acc_img, char_rect.width, char_rect.height)
            screen.blit(acc_img, char_rect)

    # Accessoires futurs — semi-transparents + pastille
    for item in outfit["future_accessories"]:
        acc_img = load_image(os.path.join(acc_dir, f"{item['accessory']}.png"))
        if acc_img:
            acc_img = fit_image(acc_img, char_rect.width, char_rect.height)
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

    # Barre d'info en bas
    font_info = pygame.font.SysFont("sans-serif", 22)
    deg = "°C" if config.get("units", "metric") == "metric" else "°F"
    temp_part = f"{current_weather['temp']:.0f}{deg}"
    desc = current_weather["description"]
    temp_str = i18n.substitute(
        config, "weather_bar", temp=temp_part, description=desc
    )
    info_surf = font_info.render(
        temp_str, True, _primary_text_color_for_rgb(circle_background_color(config))
    )
    screen.blit(info_surf, info_surf.get_rect(center=(screen_w // 2, screen_h - 24)))

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

import os
import pygame

import i18n
import character_assets


DEFAULT_BACKGROUND_COLOR = (255, 255, 255)
TEXT_ON_LIGHT_BG = (40, 40, 40)
TEXT_ON_DARK_BG = (245, 245, 245)
BADGE_BG_COLOR = (50, 50, 50)
BADGE_TEXT_COLOR = (255, 255, 255)
FUTURE_ALPHA = 120  # transparence des accessoires futurs


def background_color(config):
    """Couleur de fond depuis config (RGB 0–255). Défaut blanc si absent ou invalide."""
    raw = config.get("background_color")
    if isinstance(raw, str) and len(raw) == 7 and raw.startswith("#"):
        try:
            return tuple(int(raw[i : i + 2], 16) for i in (1, 3, 5))
        except ValueError:
            return DEFAULT_BACKGROUND_COLOR
    if isinstance(raw, (list, tuple)) and len(raw) == 3:
        return tuple(max(0, min(255, int(c))) for c in raw)
    return DEFAULT_BACKGROUND_COLOR


def primary_text_color(config):
    """Texte lisible selon la luminance du fond (BT.601)."""
    r, g, b = background_color(config)
    luminance = 0.299 * r + 0.587 * g + 0.114 * b
    return TEXT_ON_DARK_BG if luminance < 140 else TEXT_ON_LIGHT_BG


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
    badge_surf = pygame.Surface((radius * 2, radius * 2), pygame.SRCALPHA)
    pygame.draw.circle(badge_surf, BADGE_BG_COLOR, (radius, radius), radius)
    badge_surf.blit(
        text_surf,
        (radius - text_surf.get_width() // 2, radius - text_surf.get_height() // 2),
    )
    surface.blit(badge_surf, (center[0] - radius, center[1] - radius))


def render(screen, outfit, current_weather, images_dir, config):
    screen_w = config["screen_width"]
    screen_h = config["screen_height"]

    screen.fill(background_color(config))

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
            # Pastille en bas à droite de l'accessoire
            badge_text = f"{item['hour']}H"
            badge_center = (char_rect.right - 20, char_rect.bottom - 20)
            draw_badge(screen, badge_text, badge_center)

    # Barre d'info en bas
    font_info = pygame.font.SysFont("sans-serif", 22)
    deg = "°C" if config.get("units", "metric") == "metric" else "°F"
    temp_part = f"{current_weather['temp']:.0f}{deg}"
    desc = current_weather["description"]
    temp_str = i18n.substitute(
        config, "weather_bar", temp=temp_part, description=desc
    )
    info_surf = font_info.render(temp_str, True, primary_text_color(config))
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

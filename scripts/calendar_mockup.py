"""Maquette autonome de l'agenda familial, 800×480.

Ne contacte ni iCloud, ni la météo, ni la STM. Le décor reprend la géométrie
déjà calculée pour les cartes bus/métro. Les flèches changent de scénario,
S enregistre le scénario courant, Échap quitte.

    PYTHONPATH=src python3 scripts/calendar_mockup.py
    PYTHONPATH=src python3 scripts/calendar_mockup.py --export cache/calendar_mockup
"""

from __future__ import annotations

import argparse
import os
import sys
from datetime import datetime, timedelta, time as dtime

import pygame

from weatherdress import character_assets
from weatherdress import display
from weatherdress import future_accessories_column
from weatherdress import layout_config
from weatherdress import transit as transit_module
from weatherdress.config_file import load_config
from weatherdress.paths import IMAGES_DIR, REPO_ROOT

from weatherdress.calendar_panel import (
    ELLIPSIS,
    TIME_GAP,
    TODAY_TIME,
    Event,
    fit_ellipsis,
    layout_agenda,
    paint_agenda,
    should_show_agenda,
    _pick_style,
)

SCREEN_SIZE = (800, 480)
FAKE_TRANSIT = {
    "bus": {
        "56220": {"route": "51", "label": "Snowdon", "minutes": [4, 12]},
        "56221": {"route": "160", "label": "St-Michel", "minutes": [8, 18]},
    },
    "metro": {
        "Station Snowdon": [3, 9],
        "Station Saint-Michel": [5, 11],
    },
}

SCENARIOS = (
    ("journee-type", "Journée type"),
    ("titres-longs", "Titres longs"),
    ("journee-chargee", "Journée chargée"),
    ("aujourd-hui-vide", "Aujourd'hui vide"),
    ("fenetre-vide", "Fenêtre vide"),
)


class FrameResult:
    def __init__(self, weather_top, transit_top, panel, show_agenda, pieces):
        self.weather_top = weather_top
        self.transit_top = transit_top
        self.panel = panel
        self.show_agenda = show_agenda
        self.pieces = pieces


def _span(day, hour, minute, hours, title):
    start = datetime.combine(day, dtime(hour, minute))
    return Event(start, start + timedelta(hours=hours), title)


def _all_day(day, title, length=1):
    start = datetime.combine(day, dtime.min)
    end = datetime.combine(day + timedelta(days=length), dtime.min)
    return Event(start, end, title, all_day=True)


def _later(now, hour, minute, title, hours=1):
    """Heure fixe si elle est encore devant `now`, sinon plus tard dans la journée."""
    start = datetime.combine(now.date(), dtime(hour, minute))
    if start <= now:
        start = (now + timedelta(hours=1)).replace(minute=0, second=0, microsecond=0)
    end = start + timedelta(hours=hours)
    if end.date() != now.date():
        end = datetime.combine(now.date() + timedelta(days=1), dtime.min)
    if end <= start:
        return None
    return Event(start, end, title)


LONG_TITLE = (
    "Répétition générale du spectacle de fin d'année à l'école du quartier"
)
LONG_TITLE_2 = (
    "Souper d'anniversaire surprise chez les grands-parents avec toute la famille"
)


def events_for_scenario(key, now):
    today = now.date()
    tomorrow = today + timedelta(days=1)
    day2 = today + timedelta(days=2)
    day3 = today + timedelta(days=3)
    if key == "journee-type":
        start = now.replace(minute=0, second=0, microsecond=0)
        current = Event(start, start + timedelta(hours=1, minutes=15), "Cours de natation")
        later = _later(now, 16, 40, "Piano", 1)
        events = [
            current,
            _span(tomorrow, 9, 10, 1, "Dentiste"),
            _span(day3, 15, 0, 2, "Anniversaire de Lina"),
        ]
        if later:
            events.append(later)
        return events
    if key == "titres-longs":
        first = _later(now, 11, 5, LONG_TITLE, 2)
        second = _later(now, 18, 10, LONG_TITLE_2, 2)
        events = [
            event
            for event in (first, second)
            if event is not None
        ]
        events.extend(
            [
                _span(tomorrow, 9, 0, 3, LONG_TITLE),
                _span(tomorrow, 14, 30, 1, LONG_TITLE_2),
                _span(tomorrow, 18, 0, 2, "Conseil de classe et rencontre avec les enseignants"),
                _span(day2, 8, 45, 1, "Orthodontiste"),
            ]
        )
        return events
    if key == "journee-chargee":
        specs = (
            (10, 0, "Médiathèque"),
            (11, 30, "Soccer au parc"),
            (13, 0, "Dîner chez papi"),
            (15, 10, "Orthophoniste"),
            (17, 40, "Épicerie"),
            (20, 0, "Film en famille"),
        )
        events = []
        for hour, minute, title in specs:
            event = _later(now, hour, minute, title, 1)
            if event:
                events.append(event)
        events.append(_span(tomorrow, 12, 15, 1, "Cours de dessin"))
        return events
    if key == "aujourd-hui-vide":
        return [
            _all_day(tomorrow, "Vacances chez mamie"),
            _span(day2, 8, 30, 1, "Rendez-vous école"),
            _span(day3, 19, 0, 2, "Souper"),
        ]
    if key == "fenetre-vide":
        return []
    raise KeyError(key)


def sample_weather(now):
    return {
        "temp": 3.0,
        "description": "ciel dégagé",
        "condition_id": 800,
        "icon": "01d",
        "clouds": 8,
        "hour": now.hour,
        "now_ts": int(now.timestamp()),
        "wind_kmh": 12,
        "rain": 0,
        "snow": 0,
    }


def sample_outfit():
    return {
        "character": "normal_woman1",
        "current_accessories": [],
        "future_accessories": [],
    }


def _draw_background(screen, config, weather, images_dir):
    screen_w, screen_h = screen.get_size()
    bg_surf = None
    if config.get("use_weather_background", True):
        bg_surf = display._get_scaled_background_surface(
            images_dir, weather, screen_w, screen_h
        )
    if bg_surf:
        from weatherdress import ambient_background

        ambient = ambient_background.resolve_ambient_background(weather, config)
        if ambient:
            fill_rgb, alpha = ambient
            screen.fill(fill_rgb)
        else:
            screen.fill(display.background_color(config))
            alpha = display.weather_background_alpha_255(config)
        if alpha < 255:
            faded = bg_surf.copy()
            faded.set_alpha(alpha)
            screen.blit(faded, (0, 0))
        else:
            screen.blit(bg_surf, (0, 0))
    else:
        screen.fill(display.background_color(config))
    return bg_surf


def measure_scene(screen, config, images_dir, now):
    """Géométrie du décor, identique quel que soit le scénario d'agenda."""
    screen_w, screen_h = screen.get_size()
    weather = sample_weather(now)
    outfit = sample_outfit()
    usable_h = max(120, screen_h - display.transit_panel_reserved_height(config))
    layout = layout_config.effective_layout(config)
    use_photo = bool(
        config.get("use_weather_background", True)
        and display._get_scaled_background_surface(
            images_dir, weather, screen_w, screen_h
        )
    )
    use_circle = not use_photo
    top_safe = display.display_top_safe_margin(screen_h, layout)

    chars_dir = os.path.join(images_dir, "characters")
    char_path = character_assets.resolve_character_png(chars_dir, outfit["character"])
    char_img_src = display.load_image(char_path) if char_path else None
    char_center_x = int(screen_w * float(layout["character_center_x_pct"]))
    char_y_fallback = usable_h // 2 + int(layout["character_center_y_offset_px"])
    char_max_h = int(usable_h * float(layout["character_max_height_pct"]))
    char_max_w = int(screen_w * float(layout["character_max_width_pct"]))
    if char_img_src:
        char_img = display.fit_image(char_img_src, char_max_w, char_max_h)
        char_img = display.apply_character_colorkey(char_img, config)
        char_rect = char_img.get_rect()
        char_rect.centerx = char_center_x
        char_rect.centery = char_y_fallback
    else:
        char_img = None
        char_rect = pygame.Rect(0, 0, 200, 350)
        char_rect.centerx = char_center_x
        char_rect.centery = char_y_fallback
    display._place_character_rect(
        char_rect,
        char_center_x=char_center_x,
        char_y_fallback=char_y_fallback,
        screen_h=screen_h,
        top_safe_margin=top_safe,
    )
    margin_right = max(
        16, int(screen_w * float(layout["weather_screen_right_margin_pct"]))
    )
    weather_prep = display._weather_block_layout(
        config,
        weather,
        screen_w,
        screen_h,
        use_photo,
        use_circle,
        char_rect,
        layout,
    )
    block_top_y = None
    transit_start_y = None
    v_off = int(layout.get("weather_transit_vertical_offset_px", 0))
    top_safe_weather = top_safe + 4
    transit_panel_h = 0
    if layout.get("weather_mode", "after_character") == "after_character":
        transit_rows = []
        transit_row_stride = display.transit_card_layout(config)["row_stride"]
        if transit_module.transit_config_enabled(config):
            transit_rows, transit_row_stride = display._transit_panel_build_rows(
                FAKE_TRANSIT,
                config,
                screen_h=screen_h,
                start_y=0,
                transit_phase_t=0.0,
            )
            transit_panel_h = display.transit_panel_content_height(
                transit_rows, transit_row_stride
            )
        block_top_y, transit_start_y = display.plan_right_column_vertical_layout(
            char_rect,
            weather_prep["weather_total_h"],
            transit_panel_h,
            screen_h,
            top_safe_weather,
            v_off,
        )
        if transit_start_y is not None:
            max_rows = display.transit_max_rows_from_start_y(
                screen_h, transit_start_y, transit_row_stride
            )
            if max_rows < len(transit_rows):
                transit_rows = transit_rows[:max_rows]
                transit_panel_h = display.transit_panel_content_height(
                    transit_rows, transit_row_stride
                )
                block_top_y, transit_start_y = display.plan_right_column_vertical_layout(
                    char_rect,
                    weather_prep["weather_total_h"],
                    transit_panel_h,
                    screen_h,
                    top_safe_weather,
                    v_off,
                )
    right_x = screen_w - margin_right
    column_left = weather_prep["column_left"]
    card_w = max(40, right_x - int(column_left))
    if transit_start_y is None:
        panel = pygame.Rect(int(column_left), 0, card_w, 0)
    else:
        panel = pygame.Rect(int(column_left), int(transit_start_y), card_w, int(transit_panel_h))
    return {
        "weather": weather,
        "outfit": outfit,
        "layout": layout,
        "use_photo": use_photo,
        "use_circle": use_circle,
        "usable_h": usable_h,
        "top_safe_weather": top_safe_weather,
        "char_img": char_img,
        "char_rect": char_rect,
        "weather_prep": weather_prep,
        "block_top_y": block_top_y,
        "margin_right": margin_right,
        "panel": panel,
        "weather_top": block_top_y,
        "transit_top": None if transit_start_y is None else int(transit_start_y),
    }


def paint_frame(screen, config, events, now, images_dir=IMAGES_DIR):
    metrics = measure_scene(screen, config, images_dir, now)
    _draw_background(screen, config, metrics["weather"], images_dir)
    screen_w, screen_h = screen.get_size()
    display.draw_time_pill(screen, screen_w, screen_h, metrics["layout"])
    if metrics["use_circle"]:
        top_inset = max(0, min(display.CIRCLE_TOP_INSET, metrics["usable_h"] - 1))
        usable_h = metrics["usable_h"]
        r_geom = (3 * (usable_h - top_inset) + 4) // 5
        radius = max(display.CIRCLE_RADIUS, r_geom)
        display.draw_aa_filled_circle(
            screen,
            (screen_w // 2, top_inset + radius),
            radius,
            display.circle_background_color(config),
        )
    weather_layout = display.draw_weather_text_block(
        screen,
        config,
        metrics["weather"],
        metrics["outfit"],
        screen_w,
        screen_h,
        metrics["use_photo"],
        metrics["use_circle"],
        metrics["char_rect"],
        metrics["layout"],
        usable_screen_h=metrics["usable_h"],
        block_top_y=metrics["block_top_y"],
        top_safe_px=metrics["top_safe_weather"],
        weather_prep=metrics["weather_prep"],
    )
    if metrics["char_img"] is not None:
        screen.blit(metrics["char_img"], metrics["char_rect"])
    future_accessories_column.draw_future_accessories_column(
        screen,
        metrics["outfit"]["current_accessories"],
        metrics["outfit"]["future_accessories"],
        metrics["char_rect"],
        images_dir,
        config,
    )
    panel = metrics["panel"]
    # La colonne réelle vient du dessin météo (identique à la mesure).
    if weather_layout["column_left"] != panel.x:
        panel = pygame.Rect(
            int(weather_layout["column_left"]),
            panel.y,
            max(40, (screen_w - metrics["margin_right"]) - int(weather_layout["column_left"])),
            panel.height,
        )
    show = should_show_agenda(events, now) and panel.height > 0
    pieces = []
    if show:
        laid = layout_agenda(events, now, panel)
        paint_agenda(screen, laid)
        pieces = laid.pieces
        show = laid.show
    elif (
        transit_module.transit_config_enabled(config)
        and metrics["transit_top"] is not None
    ):
        display.draw_transit_panel(
            screen,
            FAKE_TRANSIT,
            config,
            column_left=panel.x,
            start_y=panel.y,
            margin_right=metrics["margin_right"],
            bg_surf=None,
            transit_phase_t=0.0,
        )
    return FrameResult(
        metrics["weather_top"],
        metrics["transit_top"],
        panel,
        show,
        pieces,
    )


def export_frames(directory, config=None, now=None, images_dir=IMAGES_DIR):
    """Écrit les cinq PNG 800×480. Retourne les chemins."""
    if config is None:
        config = load_config()
    if now is None:
        now = datetime.now().replace(second=0, microsecond=0)
    directory = os.fspath(directory)
    os.makedirs(directory, exist_ok=True)
    pygame.display.set_mode(SCREEN_SIZE)
    paths = []
    for index, (key, _label) in enumerate(SCENARIOS, start=1):
        screen = pygame.Surface(SCREEN_SIZE)
        paint_frame(screen, config, events_for_scenario(key, now), now, images_dir)
        path = os.path.join(directory, f"{index:02d}-{key}.png")
        pygame.image.save(screen, path)
        paths.append(path)
    return paths


def _scenario_caption(index):
    _key, label = SCENARIOS[index]
    return f"WeatherDress — maquette agenda — {label}"


def main(argv=None):
    parser = argparse.ArgumentParser(description="Maquette agenda 800×480")
    parser.add_argument(
        "--export",
        metavar="DOSSIER",
        help="Écrit les cinq PNG et quitte (défaut interactif)",
    )
    args = parser.parse_args(argv)
    pygame.init()
    config = load_config()
    now = datetime.now().replace(second=0, microsecond=0)
    if args.export:
        paths = export_frames(args.export, config, now)
        for path in paths:
            print(path)
        return 0

    screen = pygame.display.set_mode(SCREEN_SIZE)
    index = 0
    pygame.display.set_caption(_scenario_caption(index))
    clock = pygame.time.Clock()
    while True:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                pygame.quit()
                return 0
            if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
                pygame.quit()
                return 0
            if event.type == pygame.KEYDOWN and event.key in (
                pygame.K_RIGHT,
                pygame.K_SPACE,
            ):
                index = (index + 1) % len(SCENARIOS)
                pygame.display.set_caption(_scenario_caption(index))
            if event.type == pygame.KEYDOWN and event.key == pygame.K_LEFT:
                index = (index - 1) % len(SCENARIOS)
                pygame.display.set_caption(_scenario_caption(index))
            if event.type == pygame.KEYDOWN and event.key == pygame.K_s:
                folder = REPO_ROOT / "cache" / "calendar_mockup"
                folder.mkdir(parents=True, exist_ok=True)
                key, _label = SCENARIOS[index]
                path = folder / f"{index + 1:02d}-{key}.png"
                pygame.image.save(screen, path)
                print(path)
        key, _label = SCENARIOS[index]
        stamp = datetime.now().replace(second=0, microsecond=0)
        paint_frame(screen, config, events_for_scenario(key, stamp), stamp)
        pygame.display.flip()
        clock.tick(30)


if __name__ == "__main__":
    sys.exit(main())

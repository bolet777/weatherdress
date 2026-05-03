import ctypes
import json
import os
import sys
import threading
import time

import pygame

from . import display
from . import i18n
from . import identity_config
from . import outfit
from . import transit as transit_module
from . import weather
from .paths import CONFIG_PATH, IMAGES_DIR


def load_config():
    if not CONFIG_PATH.is_file():
        print(
            "Erreur : config.json introuvable. "
            "Copier config.example.json vers config.json et renseigner la clé API."
        )
        sys.exit(1)
    with open(CONFIG_PATH) as f:
        return json.load(f)


def _prepare_app_desktop_name(config):
    """
    Titre affiché dans barre des tâches / listes de fenêtres (souvent « python3 » sinon).
    À appeler avant pygame.init(). Sous macOS, le dock peut garder « Python » si lancement
    via python3 -m (il faudrait un bundle .app pour le nom du bundle).
    """
    title = (i18n.t(config, "window_title") or "WeatherDress").strip() or "WeatherDress"
    if len(title) > 256:
        title = title[:256]

    os.environ.setdefault("SDL_VIDEO_X11_WMCLASS", title)

    app_id = "".join(c if c.isalnum() else "-" for c in title.lower())
    app_id = "-".join(p for p in app_id.split("-") if p) or "weatherdress"
    os.environ.setdefault("SDL_VIDEO_WAYLAND_APP_ID", app_id)

    if sys.platform.startswith("linux"):
        try:
            libc = ctypes.CDLL(None)
            short = title.encode("utf-8")[:15]
            if short:
                libc.prctl(15, short, 0, 0, 0)
        except Exception:
            pass

    if sys.platform == "darwin":
        try:
            lib = ctypes.CDLL("/usr/lib/libSystem.B.dylib")
            pthread_setname_np = lib.pthread_setname_np
            pthread_setname_np.argtypes = [ctypes.c_char_p]
            pthread_setname_np.restype = ctypes.c_int
            short = title.encode("utf-8")[:63]
            if short:
                pthread_setname_np(short)
        except Exception:
            pass

    if sys.platform == "win32":
        try:
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(
                "WeatherDress.WeatherDress.1.0"
            )
        except Exception:
            pass


def _set_window_icon(max_side=128):
    """Icône de la fenêtre / barre des tâches (dock) : images/icons/app.png."""
    path = os.path.join(IMAGES_DIR, "icons", "app.png")
    if not os.path.isfile(path):
        return
    try:
        icon = pygame.image.load(path).convert_alpha()
        iw, ih = icon.get_size()
        if iw > max_side or ih > max_side:
            s = min(max_side / iw, max_side / ih)
            icon = pygame.transform.smoothscale(
                icon, (max(1, int(iw * s)), max(1, int(ih * s)))
            )
        pygame.display.set_icon(icon)
    except pygame.error as e:
        print(f"[app] Icône fenêtre non chargée ({path}) : {e}")


def main():
    config = load_config()
    _prepare_app_desktop_name(config)

    pygame.init()
    fullscreen = config.get("fullscreen", True)
    pygame.mouse.set_visible(not fullscreen)

    flags = pygame.FULLSCREEN if fullscreen else 0
    screen = pygame.display.set_mode(
        (config["screen_width"], config["screen_height"]), flags
    )
    pygame.display.set_caption(i18n.t(config, "window_title"))
    _set_window_icon()

    rotate_identity = identity_config.identity_on_each_refresh(config)
    gender, number = outfit.pick_identity(config)

    refresh_interval = config["refresh_minutes"] * 60
    last_refresh = 0
    current_outfit = None
    current_weather_data = None
    last_weather_error = None

    transit_fetcher = None
    transit_state = {"ready": False, "error": None}
    transit_data = {"bus": {}, "metro": {}}
    last_transit_refresh = 0.0
    transit_refresh_secs = 30
    if transit_module.transit_config_enabled(config):
        transit_fetcher = transit_module.TransitFetcher(config)
        transit_refresh_secs = int(
            config.get("transit", {}).get("transit_refresh_seconds", 30)
        )

        def _init_transit():
            try:
                transit_fetcher.initialize()
                transit_state["ready"] = True
            except Exception as e:
                transit_state["error"] = str(e)
                print(f"[transit] Échec initialisation : {e}")

        threading.Thread(target=_init_transit, daemon=True).start()

    clock = pygame.time.Clock()

    while True:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                pygame.quit()
                sys.exit()
            if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
                pygame.quit()
                sys.exit()

        now = time.time()
        if transit_fetcher and transit_state["ready"]:
            transit_due = (last_transit_refresh == 0.0) or (
                now - last_transit_refresh >= transit_refresh_secs
            )
            if transit_due:
                transit_data = {
                    "bus": transit_fetcher.get_bus_departures(),
                    "metro": transit_fetcher.get_metro_departures(),
                }
                last_transit_refresh = now

        if now - last_refresh >= refresh_interval:
            try:
                lang = i18n.effective_language(config)
                current_weather_data = weather.get_current_weather(
                    config["api_key"],
                    config["city"],
                    config["units"],
                    lang=lang,
                )
                forecast = weather.get_forecast(
                    config["api_key"],
                    config["city"],
                    hours=config["forecast_hours"],
                    units=config["units"],
                    lang=lang,
                )
                if rotate_identity:
                    gender, number = outfit.pick_identity(config)
                current_outfit = outfit.get_outfit_with_identity(
                    current_weather_data, forecast, gender, number
                )
                last_weather_error = None
                last_refresh = now
            except Exception as e:
                err = str(e)
                print(i18n.t(config, "console_weather_error", error=e))
                last_weather_error = err
                # On garde l'affichage précédent, on réessaie dans 5 minutes
                last_refresh = now - refresh_interval + 300

        if current_outfit and current_weather_data:
            display.render(
                screen,
                current_outfit,
                current_weather_data,
                IMAGES_DIR,
                config,
                transit_data=transit_data
                if transit_module.transit_config_enabled(config)
                else None,
                transit_phase_t=now,
            )
        elif last_weather_error:
            display.render_status(
                screen,
                config,
                [
                    i18n.t(config, "error_weather_title"),
                    i18n.t(config, "error_api_key_hint"),
                    last_weather_error[:120],
                ],
            )
        else:
            display.render_status(
                screen, config, [i18n.t(config, "weather_loading")]
            )

        clock.tick(1)  # 1 fps suffit, c'est une appli statique


if __name__ == "__main__":
    main()

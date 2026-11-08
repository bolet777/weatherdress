import ctypes
import math
import os
import sys
import threading
import time
from datetime import datetime

import pygame

from . import calendar_feed
from . import calendar_panel
from . import debug_preview
from . import display
from . import i18n
from . import ticker as ticker_module
from . import identity_config
from . import outfit
from . import transit as transit_module
from . import weather
from .config_file import load_config
from .paths import IMAGES_DIR


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


def _freeze(value):
    """Rend une valeur comparable d'une image à l'autre."""
    if isinstance(value, dict):
        return tuple(sorted((str(key), _freeze(item)) for key, item in value.items()))
    if isinstance(value, (list, tuple)):
        return tuple(_freeze(item) for item in value)
    return value


def _phase_bucket(now, seconds):
    try:
        period = float(seconds or 0)
    except (TypeError, ValueError):
        period = 0
    if period <= 0:
        return 0
    return int(now // period)


def _transit_period(config):
    block = config.get("transit") if isinstance(config.get("transit"), dict) else {}
    try:
        period = float(block.get("transit_alternate_seconds", 5) or 0)
    except (TypeError, ValueError):
        period = 5.0
    return period if period > 0 else 0.0


def _stop_counts(transit):
    data = transit or {}
    bus_n = max(1, len(data.get("bus") or {}))
    metro_n = max(1, len(data.get("metro") or {}))
    return bus_n, metro_n


def _calendar_rotates(config, events):
    """Vrai quand l'agenda et le transport échangent vraiment leur place."""
    if not events or not transit_module.transit_config_enabled(config):
        return False
    block = config.get("calendar") if isinstance(config.get("calendar"), dict) else None
    if not isinstance(block, dict) or block.get("enabled") is not True:
        return False
    if calendar_panel.rotate_period(config) <= 0:
        return False
    return calendar_panel.should_show_agenda(events, datetime.now().astimezone())


def scene_stamp(config, *, weather, outfit, transit, events, now, notice, debug_label, size):
    """Données de la scène, sans le défilement ni l'alternance des cartes.

    L'alternance toutes les quelques secondes réutilise une vue déjà dessinée.
    """
    clock = time.localtime(now)
    return (
        size,
        (clock.tm_year, clock.tm_mon, clock.tm_mday, clock.tm_hour, clock.tm_min),
        _freeze(weather),
        _freeze(outfit),
        _freeze(transit),
        _freeze(events),
        notice,
        debug_label,
    )


def view_catalog(config, transit, events):
    """Couples (phase transport, phase agenda) réellement distincts."""
    bus_n, metro_n = _stop_counts(transit)
    if _transit_period(config) <= 0:
        transit_phases = (0,)
    else:
        transit_phases = tuple(range(math.lcm(bus_n, metro_n)))
    if _calendar_rotates(config, events):
        calendar_phases = (0, 1)
    else:
        calendar_phases = (0,)
    return tuple((t_phase, c_phase) for t_phase in transit_phases for c_phase in calendar_phases)


def current_view(config, transit, events, now):
    """Vue affichée à cet instant. Elle revient sur une vue déjà cataloguée."""
    bus_n, metro_n = _stop_counts(transit)
    t_period = _transit_period(config)
    if t_period <= 0:
        t_phase = 0
    else:
        t_phase = _phase_bucket(now, t_period) % math.lcm(bus_n, metro_n)
    if _calendar_rotates(config, events):
        c_phase = _phase_bucket(now, calendar_panel.rotate_period(config)) % 2
    else:
        c_phase = 0
    return (t_phase, c_phase)


def _build_scene_cache(size, config, *, outfit, weather, transit, events, error):
    """Une image par alternance transport / agenda. Le bandeau n'y est pas dessiné."""
    cache = {}
    if not (outfit and weather):
        surface = pygame.Surface(size)
        if error:
            display.render_status(
                surface,
                config,
                [
                    i18n.t(config, "error_weather_title"),
                    i18n.t(config, "error_api_key_hint"),
                    error[:120],
                ],
                present=False,
                paint_ticker=False,
            )
        else:
            display.render_status(
                surface,
                config,
                [i18n.t(config, "weather_loading")],
                present=False,
                paint_ticker=False,
            )
        cache[None] = surface
        return cache

    t_period = _transit_period(config)
    c_period = calendar_panel.rotate_period(config)
    for t_phase, c_phase in view_catalog(config, transit, events):
        surface = pygame.Surface(size)
        display.render(
            surface,
            outfit,
            weather,
            IMAGES_DIR,
            config,
            transit_data=transit,
            transit_phase_t=(t_phase * t_period) if t_period else 0,
            calendar_events=events,
            calendar_phase_t=(c_phase * c_period) if c_period else 0,
            shown_at=None,
            present=False,
            paint_ticker=False,
        )
        cache[(t_phase, c_phase)] = surface
    return cache


def _compose(screen, scene, config, now):
    """Colle la scène déjà dessinée, puis seulement le bandeau."""
    screen.blit(scene, (0, 0))
    if ticker_module.band_height(config):
        ticker_module.paint(screen, config, now)
    pygame.display.flip()


def _open_display(config):
    """
    Plein écran : résolution native du moniteur (Pygame 0×0 + FULLSCREEN).
    Fenêtre : screen_width / screen_height dans config.json.
    """
    fullscreen = config.get("fullscreen", True)
    pygame.mouse.set_visible(not fullscreen)
    if fullscreen:
        return pygame.display.set_mode((0, 0), pygame.FULLSCREEN)
    w = int(config.get("screen_width", 800))
    h = int(config.get("screen_height", 480))
    return pygame.display.set_mode((w, h))


def main():
    config = load_config()
    _prepare_app_desktop_name(config)

    pygame.init()
    screen = _open_display(config)
    pygame.display.set_caption(i18n.t(config, "window_title"))
    _set_window_icon()
    band_px = ticker_module.band_height(config)
    if band_px and ticker_module.scrolling(config):
        print(f"[ticker] Bandeau actif, {band_px} px, texte en défilement.")
    elif band_px:
        print(f"[ticker] Bandeau actif, {band_px} px, sans texte.")
    else:
        print("[ticker] Bandeau coupé.")

    rotate_identity = identity_config.identity_on_each_refresh(config)
    chars_dir = os.path.join(IMAGES_DIR, "characters")
    gender, number = outfit.pick_identity(config, chars_dir)

    refresh_interval = config["refresh_minutes"] * 60
    last_refresh = 0
    current_outfit = None
    current_weather_data = None
    last_weather_error = None

    debug_preview_mode = bool(config.get("debug_preview"))
    debug_controller = (
        debug_preview.DebugPreview(config) if debug_preview_mode else None
    )

    transit_fetcher = None
    transit_state = {"metro_ready": False, "error": None}
    transit_data = {"bus": {}, "metro": {}}
    transit_refresh_secs = 30
    if transit_module.transit_config_enabled(config):
        transit_fetcher = transit_module.TransitFetcher(config)
        transit_refresh_secs = int(
            config.get("transit", {}).get("transit_refresh_seconds", 30)
        )

        def _init_metro_index():
            try:
                transit_fetcher.initialize()
                transit_state["metro_ready"] = True
            except Exception as e:
                transit_state["error"] = str(e)
                print(f"[transit] Échec initialisation métro : {e}")

        threading.Thread(target=_init_metro_index, daemon=True).start()

        transit_lock = threading.Lock()

        def _poll_transit():
            """Réseau hors de l'affichage : le texte ne s'arrête pas pendant la requête."""
            while True:
                bus = {}
                metro = None
                try:
                    bus = transit_fetcher.get_bus_departures()
                    if transit_state["metro_ready"]:
                        metro = transit_fetcher.get_metro_departures()
                except Exception as exc:
                    print(f"[transit] Lecture impossible : {exc}")
                with transit_lock:
                    transit_data["bus"] = bus
                    if metro is not None:
                        transit_data["metro"] = metro
                time.sleep(max(1, transit_refresh_secs))

        threading.Thread(target=_poll_transit, daemon=True).start()

    # Le cache valide est chargé avant le thread réseau. La boucle ne lit que l'instantané.
    calendar_fetcher = calendar_feed.start_in_background(config)

    clock = pygame.time.Clock()
    scene_cache = {}
    scene_stamp_value = None

    while True:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                pygame.quit()
                sys.exit()
            if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
                pygame.quit()
                sys.exit()

        now = time.time()
        if transit_fetcher:
            with transit_lock:
                transit_snapshot = {
                    "bus": dict(transit_data.get("bus") or {}),
                    "metro": dict(transit_data.get("metro") or {}),
                }
        else:
            transit_snapshot = transit_data

        debug_label = None
        if debug_controller is not None:
            frame = debug_controller.next_frame(now, gender, number)
            current_weather_data = frame["weather"]
            current_outfit = frame["outfit"]
            debug_label = frame["label"]
            last_weather_error = None
            pygame.display.set_caption(
                f"{i18n.t(config, 'window_title')} — {frame['label']}"
            )
        elif now - last_refresh >= refresh_interval:
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
                    gender, number = outfit.pick_identity(
                        config, chars_dir, current_weather_data
                    )
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

        transit_for_render = None
        if transit_module.transit_config_enabled(config):
            transit_for_render = transit_module.merge_transit_display_data(
                config,
                transit_snapshot,
                metro_ready=transit_state["metro_ready"],
            )

        calendar_events = calendar_feed.events_for_render(calendar_fetcher)
        if current_outfit and current_weather_data:
            notice = None
        elif last_weather_error:
            notice = ("error", last_weather_error[:120])
        else:
            notice = ("loading",)
        stamp = scene_stamp(
            config,
            weather=current_weather_data,
            outfit=current_outfit,
            transit=transit_for_render,
            events=calendar_events,
            now=now,
            notice=notice,
            debug_label=debug_label,
            size=screen.get_size(),
        )
        if stamp != scene_stamp_value:
            # Toutes les alternances sont dessinées d'un coup. Le passage
            # de l'une à l'autre, quelques secondes plus tard, ne redessine rien.
            scene_cache = _build_scene_cache(
                screen.get_size(),
                config,
                outfit=current_outfit,
                weather=current_weather_data,
                transit=transit_for_render,
                events=calendar_events,
                error=last_weather_error,
            )
            scene_stamp_value = stamp
        if current_outfit and current_weather_data:
            view = current_view(config, transit_for_render, calendar_events, now)
        else:
            view = None
        _compose(screen, scene_cache[view], config, now)
        clock.tick(ticker_module.TICKER_FPS if ticker_module.scrolling(config) else 1)


if __name__ == "__main__":
    main()

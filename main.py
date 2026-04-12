import json
import os
import sys
import time
import pygame

import weather
import outfit
import display
import i18n
import identity_config


CONFIG_PATH = os.path.join(os.path.dirname(__file__), "config.json")
IMAGES_DIR = os.path.join(os.path.dirname(__file__), "images")


def load_config():
    if not os.path.exists(CONFIG_PATH):
        print(f"Erreur : config.json introuvable. Copier config.example.json vers config.json et renseigner la clé API.")
        sys.exit(1)
    with open(CONFIG_PATH) as f:
        return json.load(f)


def main():
    config = load_config()

    pygame.init()
    fullscreen = config.get("fullscreen", True)
    pygame.mouse.set_visible(not fullscreen)

    flags = pygame.FULLSCREEN if fullscreen else 0
    screen = pygame.display.set_mode(
        (config["screen_width"], config["screen_height"]), flags
    )
    pygame.display.set_caption(i18n.t(config, "window_title"))

    rotate_identity = identity_config.identity_on_each_refresh(config)
    gender, number = outfit.pick_identity(config)

    refresh_interval = config["refresh_minutes"] * 60
    last_refresh = 0
    current_outfit = None
    current_weather_data = None
    last_weather_error = None

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
            display.render(screen, current_outfit, current_weather_data, IMAGES_DIR, config)
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

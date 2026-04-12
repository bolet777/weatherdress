import json
import os
import sys
import time
import pygame

import weather
import outfit
import display


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
    pygame.mouse.set_visible(False)

    flags = pygame.FULLSCREEN
    screen = pygame.display.set_mode(
        (config["screen_width"], config["screen_height"]), flags
    )
    pygame.display.set_caption("WeatherDress")

    # Genre et numéro fixes pour toute la session
    gender, number = outfit.pick_identity()

    refresh_interval = config["refresh_minutes"] * 60
    last_refresh = 0
    current_outfit = None
    current_weather_data = None

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
                current_weather_data = weather.get_current_weather(
                    config["api_key"], config["city"], config["units"]
                )
                forecast = weather.get_forecast(
                    config["api_key"],
                    config["city"],
                    hours=config["forecast_hours"],
                    units=config["units"],
                )
                current_outfit = outfit.get_outfit_with_identity(
                    current_weather_data, forecast, gender, number
                )
                last_refresh = now
            except Exception as e:
                print(f"Erreur météo : {e}")
                # On garde l'affichage précédent, on réessaie dans 5 minutes
                last_refresh = now - refresh_interval + 300

        if current_outfit and current_weather_data:
            display.render(screen, current_outfit, current_weather_data, IMAGES_DIR, config)

        clock.tick(1)  # 1 fps suffit, c'est une appli statique


if __name__ == "__main__":
    main()

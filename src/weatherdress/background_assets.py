import json
import os
from datetime import date

MAP_FILENAME = "background_map.json"


def load_background_map(backgrounds_dir):
    """
    Charge `background_map.json` depuis `images/backgrounds/`.
    Retourne None si le fichier est absent (fond uni uniquement).
    """
    path = os.path.join(backgrounds_dir, MAP_FILENAME)
    if not os.path.isfile(path):
        return None
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def resolve_background_key(weather, map_data, on_date=None):
    """
    Choisit une clé logique (ex. `rain`, `sunny`) selon les règles du JSON.
    `weather` doit inclure `condition_id` (OpenWeatherMap) et optionnellement `icon`.
    Si l'icône finit par `n` et que `{clé}_night` est dans `keys_to_file`, cette clé est retenue.
    De décembre à mars (`on_date`, date locale, défaut aujourd'hui), la nuit essaie
    `{clé}_winter_night`, `{clé}_night`, puis la clé. Le jour essaie `{clé}_winter`,
    puis la clé. Une variante de jour n'est jamais choisie la nuit.
    """
    if not map_data:
        return None
    cid = weather.get("condition_id")
    icon = weather.get("icon") or ""
    icon_suffix = icon[-1] if len(icon) >= 1 else None

    key = None
    if cid is not None:
        for rule in map_data.get("rules", []):
            if "condition_id" in rule:
                if cid != rule["condition_id"]:
                    continue
                if "icon_suffix" in rule:
                    want = rule["icon_suffix"]
                    if icon_suffix != want:
                        continue
                key = rule["key"]
                break
            if "condition_id_range" in rule:
                lo, hi = rule["condition_id_range"]
                if lo <= cid <= hi:
                    key = rule["key"]
                    break
    if key is None:
        key = map_data.get("default_key")
    if not key:
        return key

    if on_date is None:
        on_date = date.today()
    winter = on_date.month in (12, 1, 2, 3)
    night = icon_suffix == "n"
    keys = map_data.get("keys_to_file") or {}

    if winter and night:
        candidates = (f"{key}_winter_night", f"{key}_night", key)
    elif winter:
        candidates = (f"{key}_winter", key)
    elif night:
        candidates = (f"{key}_night", key)
    else:
        return key

    for candidate in candidates:
        if candidate in keys or candidate == key:
            return candidate
    return key


def resolve_background_image_path(images_dir, weather, map_data):
    """
    Chemin absolu vers le PNG de fond, ou None si désactivé / fichier manquant.
    """
    if not map_data:
        return None
    key = resolve_background_key(weather, map_data)
    if not key:
        return None
    filename = map_data.get("keys_to_file", {}).get(key)
    if not filename:
        return None
    path = os.path.join(images_dir, "backgrounds", filename)
    return path if os.path.isfile(path) else None

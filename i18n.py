import json
import os

_LOCALES_DIR = os.path.join(os.path.dirname(__file__), "locale")

# Si `language` est absent de config.json (anciens fichiers), on reste cohérent avec config.example.json
DEFAULT_LANGUAGE = "fr"


def effective_language(config):
    return (config.get("language") or DEFAULT_LANGUAGE).strip().lower()


def _load_locale(code):
    path = os.path.join(_LOCALES_DIR, f"{code}.json")
    if not os.path.isfile(path):
        return {}
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def messages(config):
    """Textes pour la langue demandée, complétés par l’anglais pour les clés manquantes."""
    lang = effective_language(config)
    base = _load_locale("en")
    if lang == "en":
        return base
    return {**base, **_load_locale(lang)}


def t(config, key, **kwargs):
    template = messages(config).get(key, key)
    if kwargs:
        try:
            return template.format(**kwargs)
        except (KeyError, ValueError):
            return template
    return template


def substitute(config, key, **parts):
    """Remplace {nom} dans le modèle sans interpréter le reste (ex. texte API avec accolades)."""
    text = messages(config).get(key, key)
    for name, value in parts.items():
        text = text.replace("{" + name + "}", str(value))
    return text


def format_weather_future_note(config, future_accessories):
    """Suffixe barre météo : accessoires futurs. Locales : weather_future_segment_<nom>."""
    if not future_accessories:
        return ""
    msgs = messages(config)
    parts = []
    for item in future_accessories:
        acc = item["accessory"]
        key = f"weather_future_segment_{acc}"
        hour = item["hour"]
        hours = item.get("hours_from_now", "")
        if key in msgs:
            parts.append(substitute(config, key, hour=hour, hours=hours))
        else:
            parts.append(
                substitute(
                    config,
                    "weather_future_segment_fallback",
                    hour=hour,
                    hours=hours,
                    accessory=acc,
                )
            )
    joined = ", ".join(parts)
    return substitute(config, "weather_future_note", segments=joined)

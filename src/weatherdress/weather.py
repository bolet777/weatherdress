import math
import requests
from datetime import datetime, timezone


BASE_URL = "https://api.openweathermap.org/data/2.5"


def get_current_weather(api_key, city, units="metric", lang=None):
    """Retourne les conditions météo actuelles. `lang` : code ISO pour les libellés (ex. fr, en)."""
    params = {"q": city, "appid": api_key, "units": units}
    if lang:
        params["lang"] = lang
    resp = requests.get(
        f"{BASE_URL}/weather",
        params=params,
        timeout=10,
    )
    resp.raise_for_status()
    data = resp.json()

    w0 = data["weather"][0]
    return {
        "temp": data["main"]["temp"],
        "description": w0["description"],
        "icon": w0["icon"],
        "condition_id": w0["id"],
        "wind_kmh": data["wind"]["speed"] * 3.6,
        "rain": data.get("rain", {}).get("1h", 0),
        "snow": data.get("snow", {}).get("1h", 0),
        "clouds": data["clouds"]["all"],  # pourcentage
        "hour": datetime.now().hour,
    }


def get_forecast(api_key, city, hours=8, units="metric", lang=None):
    """
    Retourne les tranches de prévision sur les prochaines `hours` heures.
    L'API gratuite fournit des tranches de 3h.
    """
    params = {"q": city, "appid": api_key, "units": units}
    if lang:
        params["lang"] = lang
    resp = requests.get(
        f"{BASE_URL}/forecast",
        params=params,
        timeout=10,
    )
    resp.raise_for_status()
    data = resp.json()

    now = datetime.now(tz=timezone.utc).timestamp()
    limit = now + hours * 3600
    slices = []

    for item in data["list"]:
        ts = item["dt"]
        if ts <= now or ts > limit:
            continue
        dt_local = datetime.fromtimestamp(ts)
        hours_from_now = max(1, math.ceil((ts - now) / 3600))
        slices.append({
            "hour": dt_local.hour,
            "hours_from_now": hours_from_now,
            "temp": item["main"]["temp"],
            "description": item["weather"][0]["description"],
            "icon": item["weather"][0]["icon"],
            "wind_kmh": item["wind"]["speed"] * 3.6,
            "rain": item.get("rain", {}).get("3h", 0),
            "snow": item.get("snow", {}).get("3h", 0),
            "clouds": item["clouds"]["all"],
        })

    return slices

import os
import random

from . import character_assets
# Pastille horaire (accessoires futurs) : fraction du rect personnage. Défaut si absent du rule.
DEFAULT_ACCESSORY_BADGE_OFFSET = (0.8, 0.2)


def _condition_id_int(w):
    """OpenWeather `id` (int) ; tolère str ou types numériques."""
    c = w.get("condition_id")
    if c is None:
        return None
    try:
        return int(c)
    except (TypeError, ValueError):
        return None


def _local_hour(w):
    try:
        return int(w.get("hour", 12))
    except (TypeError, ValueError):
        return 12


def _weather_timestamp(w):
    """Instant météo (actuel ou tranche prévision) pour lever/coucher."""
    for key in ("forecast_ts", "now_ts"):
        raw = w.get(key)
        if raw is None:
            continue
        try:
            return float(raw)
        except (TypeError, ValueError):
            continue
    return None


def _is_forecast_slice(w):
    return w.get("forecast_ts") is not None


def _rain_mm(w):
    try:
        return float(w.get("rain") or 0)
    except (TypeError, ValueError):
        return 0.0


def _rain_rate_mmh(w):
    """Pluie en mm/h : actuel = champ 1 h ; prévision 3 h → moyenne sur 3 h."""
    r = _rain_mm(w)
    if _is_forecast_slice(w):
        return r / 3.0
    return r


def _owm_is_liquid_rain_code(condition_id):
    """Codes OWM pluie / bruine / orage (hors neige)."""
    if condition_id is None:
        return False
    return (
        200 <= condition_id <= 232
        or 300 <= condition_id <= 321
        or 500 <= condition_id <= 531
    )


def _is_raining(w):
    """Pluie liquide (mm ou code météo), pas en cas de neige dominante."""
    if w.get("snow", 0) > 0:
        return False
    if _rain_mm(w) > 0:
        return True
    return _owm_is_liquid_rain_code(_condition_id_int(w))


def _cloud_cover_pct(w):
    try:
        return int(w.get("clouds", 0))
    except (TypeError, ValueError):
        return 0


def _owm_is_overcast_code(condition_id):
    """OWM 803 (nuageux) / 804 (couvert)."""
    return condition_id in (803, 804)


def _icon_implies_overcast(w):
    icon = str(w.get("icon") or "")
    return icon.startswith("04")


def _is_significantly_cloudy(w):
    """
    Temps nuageux ou couvert : pas de lunettes / casquette soleil.
    S'appuie sur le code OWM, l'icône et le pourcentage de nuages.
    """
    cid = _condition_id_int(w)
    if _owm_is_overcast_code(cid):
        return True
    if _icon_implies_overcast(w):
        return True
    return _cloud_cover_pct(w) >= 40


def _is_dry_sunny_weather(w):
    """Ciel sec : pas de pluie signalée (accessoires soleil / tête ensoleillée)."""
    return not _is_raining(w)


def _is_reasonable_daylight(w):
    """
    Jour pour accessoires « soleil » : sunrise/sunset + horodatage si dispo,
    sinon repli heure locale 6–19 (pas de lunettes/casquette/chapeau à partir de 20 h).
    """
    h = _local_hour(w)
    if h >= 20 or h < 6:
        return False

    ts = _weather_timestamp(w)
    sr, ss = w.get("sunrise"), w.get("sunset")
    if (
        ts is not None
        and isinstance(sr, int)
        and isinstance(ss, int)
        and ss > sr
    ):
        return sr <= ts <= ss
    return 6 <= h <= 19


def _is_sun_protection_time(w):
    """Fenêtre tête soleil : milieu de journée (pas en fin de soirée)."""
    h = _local_hour(w)
    return _is_reasonable_daylight(w) and 7 <= h <= 17


def _is_sunglasses_time(w):
    h = _local_hour(w)
    return _is_reasonable_daylight(w) and 6 <= h <= 17


ACCESSORY_RULES = [
    {
        "id": "umbrella",
        "predicate": _is_raining,
        "badge_offset": (0.2, 0.8),
    },
    {
        "id": "sun_screen",
        "predicate": lambda w: (
            _is_dry_sunny_weather(w)
            and not _is_significantly_cloudy(w)
            and _cloud_cover_pct(w) < 20
            and _is_reasonable_daylight(w)
        ),
        "badge_offset": (0.42, 0.12),
    },
    {
        "id": "sunglasses",
        "slot": "sun",
        "predicate": lambda w: (
            _is_dry_sunny_weather(w)
            and not _is_significantly_cloudy(w)
            and _is_sunglasses_time(w)
            and _cloud_cover_pct(w) < 20
        ),
        "badge_offset": (0.5, 0.1),
    },
    {
        "id": "beanie",
        "slot": "head",
        "predicate": lambda w: w["snow"] > 0 or w["temp"] < 7,
        "badge_offset": (0.48, 0.06),
    },
    {
        "id": "hat",
        "slot": "head",
        "predicate": lambda w: (
            _is_dry_sunny_weather(w)
            and not _is_significantly_cloudy(w)
            and _is_sun_protection_time(w)
            and (
                (_cloud_cover_pct(w) < 20 and 7 <= _local_hour(w) <= 17)
                or (w["temp"] >= 28 and _cloud_cover_pct(w) < 30)
            )
        ),
        "badge_offset": (0.5, 0.05),
    },
    {
        "id": "cap",
        "slot": "head",
        "predicate": lambda w: (
            _is_dry_sunny_weather(w)
            and not _is_significantly_cloudy(w)
            and _is_sun_protection_time(w)
            and 20 <= _cloud_cover_pct(w) < 30
            and 9 <= _local_hour(w) <= 17
            and w["temp"] < 28
        ),
        "badge_offset": (0.48, 0.07),
    },
    {
        "id": "boots",
        "slot": "feet",
        "predicate": lambda w: w["snow"] > 0,
        "badge_offset": (0.7, 0.85),
    },
    {
        "id": "rain_boots",
        "slot": "feet",
        "predicate": lambda w: _rain_rate_mmh(w) > 3 and w["snow"] <= 0,
        "badge_offset": (0.76, 0.88),
    },
    {
        "id": "scarf",
        "predicate": lambda w: w["temp"] < 5
        or (w["wind_kmh"] > 30 and w["temp"] <= 18),
        "badge_offset": (0.6, 0.4),
    },
    {
        "id": "crampons",
        "predicate": lambda w: _condition_id_int(w) == 511
        or (
            w.get("snow", 0) <= 0
            and _is_raining(w)
            and w["temp"] <= 2
        ),
        "badge_offset": (0.62, 0.82),
    },
]


def accessory_badge_offset(accessory_id):
    """Position relative de la pastille pour un accessoire futur (sinon défaut)."""
    for rule in ACCESSORY_RULES:
        if rule["id"] == accessory_id:
            return rule.get("badge_offset", DEFAULT_ACCESSORY_BADGE_OFFSET)
    return DEFAULT_ACCESSORY_BADGE_OFFSET


# Seuils de température pour le personnage de base
def character_type(temp, snow):
    if snow > 0:
        return "snow"
    if temp >= 28:
        return "veryhot"
    if temp >= 25:
        return "hot"
    if temp >= 17:
        return "normal"
    if temp >= -9:
        return "cold"
    return "verycold"


def character_sprite_prefix(ctype):
    """Préfixe des fichiers PNG (verycold/veryhot n'ont pas de dossier dédié dans les assets)."""
    if ctype == "verycold":
        return "cold"
    if ctype == "veryhot":
        return "hot"
    return ctype


def pick_identity(config=None, characters_dir=None, current_weather=None):
    """
    Choisit genre et numéro de variante.

    Si ``characters_dir`` pointe vers ``images/characters``, les numéros possibles
    sont ceux pour lesquels un PNG existe pour le préfixe météo courant (ou
    ``normal`` si pas encore de météo). Tirage uniforme dans cette liste.

    Clé optionnelle ``character_variant_max`` (> 0) : clip de la liste
    (n <= max). Si le répertoire est absent ou vide, repli sur l’ancien tirage
    ``1…character_variant_max`` (défaut 6).
    """
    cfg = config or {}
    gender = random.choice(["woman", "man"])

    def _fallback_randint():
        max_n = int(cfg.get("character_variant_max", 6))
        max_n = max(1, min(max_n, 99))
        return random.randint(1, max_n)

    if not characters_dir or not os.path.isdir(characters_dir):
        return gender, _fallback_randint()

    if current_weather is not None:
        ctype = character_type(current_weather["temp"], current_weather["snow"])
        prefix = character_sprite_prefix(ctype)
    else:
        prefix = "normal"

    nums = character_assets.list_character_variant_numbers(
        characters_dir, prefix, gender
    )
    if not nums:
        return gender, _fallback_randint()

    raw_cap = cfg.get("character_variant_max")
    try:
        cap = int(raw_cap) if raw_cap is not None else None
    except (TypeError, ValueError):
        cap = None
    if cap is not None and cap > 0:
        clipped = [n for n in nums if n <= cap]
        if clipped:
            nums = clipped

    number = random.choice(nums)
    return gender, number


def _with_sun_times(weather, sunrise, sunset):
    """Propage lever/coucher sur une tranche prévision pour le jour/nuit."""
    if sunrise is None and sunset is None:
        return weather
    out = dict(weather)
    if sunrise is not None and "sunrise" not in out:
        out["sunrise"] = sunrise
    if sunset is not None and "sunset" not in out:
        out["sunset"] = sunset
    return out


def active_accessories(weather):
    """
    Retourne la liste des accessoires actifs pour une tranche météo donnée.
    `weather` est un dict avec temp, rain, snow, wind_kmh, clouds, hour
    et optionnellement condition_id (OpenWeather), now_ts, sunrise, sunset.
    Règles avec le même `slot` : seule la première qui matche dans ACCESSORY_RULES est gardée.
    """
    out = []
    filled_slots = set()
    for rule in ACCESSORY_RULES:
        if not rule["predicate"](weather):
            continue
        slot = rule.get("slot")
        if slot is not None:
            if slot in filled_slots:
                continue
            filled_slots.add(slot)
        out.append(rule["id"])
    return out


def get_outfit(current_weather, forecast_slices):
    """
    Retourne un dict décrivant la tenue complète :
    - character: nom du fichier de base (ex: "cold_woman1")
    - current_accessories: liste de noms d'accessoires pour maintenant
    - future_accessories: liste de dicts {accessory, hour} pour les prochaines tranches
    """
    # L'identité est passée depuis main.py pour rester stable
    raise NotImplementedError("Utiliser get_outfit_with_identity()")


def get_outfit_with_identity(current_weather, forecast_slices, gender, number):
    ctype = character_type(current_weather["temp"], current_weather["snow"])
    prefix = character_sprite_prefix(ctype)
    character = f"{prefix}_{gender}{number}"

    current_acc = active_accessories(current_weather)

    # Pour chaque tranche future, calcule les accessoires et garde les nouveaux
    future_acc = []
    seen = set(current_acc)
    sr = current_weather.get("sunrise")
    ss = current_weather.get("sunset")
    for slice_ in forecast_slices:
        for acc in active_accessories(_with_sun_times(slice_, sr, ss)):
            if acc not in seen:
                future_acc.append(
                    {
                        "accessory": acc,
                        "hour": slice_["hour"],
                        "hours_from_now": slice_.get("hours_from_now", 1),
                    }
                )
                seen.add(acc)

    future_acc.sort(key=lambda a: float(a.get("hours_from_now") or 0))
    return {
        "character": character,
        "current_accessories": current_acc,
        "future_accessories": future_acc,
    }

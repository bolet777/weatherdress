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


def _is_reasonable_daylight(w):
    """
    Jour pour accessoires « soleil » : sunrise/sunset + now_ts si dispo (API current),
    sinon repli heure locale 6–20 (prévisions / dicts sans now_ts).
    """
    now_ts = w.get("now_ts")
    sr, ss = w.get("sunrise"), w.get("sunset")
    if (
        now_ts is not None
        and isinstance(sr, int)
        and isinstance(ss, int)
        and ss > sr
    ):
        try:
            ts = float(now_ts)
        except (TypeError, ValueError):
            pass
        else:
            return sr <= ts <= ss
    try:
        h = int(w.get("hour", 12))
    except (TypeError, ValueError):
        h = 12
    return 6 <= h <= 20


ACCESSORY_RULES = [
    {
        "id": "umbrella",
        "predicate": lambda w: w["rain"] > 0,
        "badge_offset": (0.2, 0.8),
    },
    {
        "id": "sun_screen",
        "predicate": lambda w: w["clouds"] < 20 and _is_reasonable_daylight(w),
        "badge_offset": (0.42, 0.12),
    },
    {
        "id": "sunglasses",
        "slot": "sun",
        "predicate": lambda w: _is_reasonable_daylight(w)
        and (w["clouds"] < 30 or w["temp"] >= 28),
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
            (w["clouds"] < 20 and 7 <= w["hour"] <= 17) or w["temp"] >= 28
        ),
        "badge_offset": (0.5, 0.05),
    },
    {
        "id": "cap",
        "slot": "head",
        "predicate": lambda w: (
            w["clouds"] < 30
            and 9 <= w["hour"] <= 17
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
        "predicate": lambda w: w["rain"] > 3 and w["snow"] <= 0,
        "badge_offset": (0.76, 0.88),
    },
    {
        "id": "scarf",
        "predicate": lambda w: w["temp"] < 5 or w["wind_kmh"] > 30,
        "badge_offset": (0.6, 0.4),
    },
    {
        "id": "crampons",
        "predicate": lambda w: _condition_id_int(w) == 511
        or (
            w.get("snow", 0) <= 0
            and w.get("rain", 0) > 0
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
    for slice_ in forecast_slices:
        for acc in active_accessories(slice_):
            if acc not in seen:
                future_acc.append(
                    {
                        "accessory": acc,
                        "hour": slice_["hour"],
                        "hours_from_now": slice_.get("hours_from_now", 1),
                    }
                )
                seen.add(acc)

    return {
        "character": character,
        "current_accessories": current_acc,
        "future_accessories": future_acc,
    }

"""
Icônes météo (PNG dans images/icons/weather/) à partir du code condition OpenWeatherMap
(`weather[0].id`) et éventuellement `weather[0].icon` (suffixe jour/nuit d/n).

Référence : https://openweathermap.org/weather-conditions
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Optional, Tuple

# Fichier de repli : nuage générique (présent dans le pack)
FALLBACK_FILENAME = "cloudy.png"

HeavyRainIds = frozenset({502, 503, 504, 522})
FreezingRainId = frozenset({511})
SleetSnowIds = frozenset({611, 612, 613, 615, 616})


def _icon_suffix(icon: Optional[str]) -> Optional[str]:
    if not icon or not isinstance(icon, str):
        return None
    s = icon.strip()
    return s[-1].lower() if s else None


def resolve_weather_icon_filename(
    condition_id: Optional[int], icon: Optional[str] = None
) -> Tuple[str, bool]:
    """
    Retourne (nom_fichier_png, utilise_fallback_direct).
    `utilise_fallback_direct` est True si la résolution passe par FALLBACK_FILENAME
    (code inconnu, None, ou atmosphère sans pictogramme dédié ex. volcanic ash).

    Codes couverts exhaustivement comme l’API Conditions courantes (200–804 + extensions
    tornado ouragan si renvoyés).
    """
    if condition_id is None:
        return (FALLBACK_FILENAME, True)

    cid = int(condition_id)

    # Orages — pictogramme foudre
    if 200 <= cid <= 232:
        return ("thunder.png", False)

    # Bruine
    if 300 <= cid <= 321:
        return ("drizzle.png", False)

    # Pluie (intensités)
    if 500 <= cid <= 531:
        if cid in FreezingRainId:
            return ("sleet.png", False)
        if cid in HeavyRainIds:
            return ("heavy-rain.png", False)
        return ("rainy.png", False)

    # Neige / grésil / mélange
    if 600 <= cid <= 622:
        if cid in SleetSnowIds:
            return ("sleet.png", False)
        return ("snowy.png", False)

    # Atmosphère (701–781)
    if cid == 701:
        return ("misty.png", False)
    if cid == 711:
        return ("foggy.png", False)
    if cid == 721:
        return ("foggy.png", False)
    if cid == 731:
        return ("windy.png", False)
    if cid == 741:
        return ("foggy.png", False)
    if cid == 751:
        return (FALLBACK_FILENAME, True)
    if cid == 761:
        return (FALLBACK_FILENAME, True)
    if cid == 762:
        return (FALLBACK_FILENAME, True)
    if cid == 771:
        return ("windy.png", False)
    if cid == 781:
        return ("tornado.png", False)

    # Clair — suffixe dernier caractère de `icon` pour jour (`d`) / nuit (`n`)
    suf = _icon_suffix(icon)
    # Clair
    if cid == 800:
        if suf == "n":
            return ("night-clear.png", False)
        return ("sunny.png", False)

    # Nuages — jour / nuit pour peu et éclaircis
    if cid in (801, 802):
        if suf == "n":
            return ("partly-cloudy-night.png", False)
        return ("partly-cloudy.png", False)

    if cid in (803, 804):
        return ("cloudy.png", False)

    return (FALLBACK_FILENAME, True)


def get_weather_icon(condition_id: Optional[int], icon: Optional[str] = None, *, images_dir: str = "") -> str:
    """
    Chemin absolu vers un PNG dans images/icons/weather/ pour cette condition.
    `images_dir` : même valeur que paths.IMAGES_DIR (répertoire `images/`).

    Alias fonctionnel pour l’usage demandé côté intégration (équivalent sémantique
    de « getWeatherIcon(conditionCode) » quand les codes proviennent de l’API).
    """
    fn, _ = resolve_weather_icon_filename(condition_id, icon)
    base = Path(images_dir) / "icons" / "weather"
    p = base / fn
    if p.is_file():
        return os.fspath(p)
    fb = base / FALLBACK_FILENAME
    if fb.is_file():
        return os.fspath(fb)
    raise FileNotFoundError(f"Aucune icône météo trouvée sous {base}")


def get_weather_icon_path(
    images_dir: str,
    condition_id: Optional[int],
    icon: Optional[str] = None,
) -> Optional[str]:
    """
    Comme get_weather_icon mais retourne None si même le fichier de secours est absent,
    au lieu de lever (pratique pour l’UI).
    """
    try:
        return get_weather_icon(condition_id, icon, images_dir=images_dir)
    except FileNotFoundError:
        return None

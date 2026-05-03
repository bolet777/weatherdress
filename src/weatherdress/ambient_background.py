"""
Couleur de remplissage et opacité du fond photo selon l'heure (soleil) et les nuages.
Sans dépendance pygame : logique pure pour tests.
"""

from datetime import datetime, timezone
from typing import Any, Dict, Optional, Tuple


def _clamp(x: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, x))


def _lerp(a: float, b: float, t: float) -> float:
    return a + (b - a) * t


def _rgb_from_config(
    config: Dict[str, Any], key: str, default: Tuple[int, int, int]
) -> Tuple[int, int, int]:
    raw = config.get(key)
    if isinstance(raw, str) and len(raw) == 7 and raw.startswith("#"):
        try:
            return tuple(max(0, min(255, int(raw[i : i + 2], 16))) for i in (1, 3, 5))  # type: ignore[return-value]
        except ValueError:
            return default
    if isinstance(raw, (list, tuple)) and len(raw) == 3:
        return tuple(max(0, min(255, int(c))) for c in raw)  # type: ignore[return-value]
    return default


def _lerp_rgb(
    a: Tuple[int, int, int],
    b: Tuple[int, int, int],
    t: float,
) -> Tuple[int, int, int]:
    t = _clamp(t, 0.0, 1.0)
    return (
        int(round(_lerp(float(a[0]), float(b[0]), t))),
        int(round(_lerp(float(a[1]), float(b[1]), t))),
        int(round(_lerp(float(a[2]), float(b[2]), t))),
    )


def weather_background_alpha_base_255(config: Dict[str, Any]) -> int:
    """Même règle que display.weather_background_alpha_255 (facteur de base ambiance)."""
    raw = config.get("weather_background_alpha", 1.0)
    try:
        a = float(raw)
    except (TypeError, ValueError):
        return 255
    if a > 1.0:
        return max(0, min(255, int(a)))
    a = max(0.0, min(1.0, a))
    return int(round(255 * a))


def day_phase_from_sun_times(
    sunrise: Optional[int],
    sunset: Optional[int],
    now_ts: float,
    twilight_seconds: float,
) -> Optional[float]:
    """
    1.0 = plein jour, 0.0 = nuit, transitions autour de sunrise/sunset.
    Retourne None si les entrées sont invalides.
    """
    if sunrise is None or sunset is None:
        return None
    if not isinstance(sunrise, int) or not isinstance(sunset, int):
        return None
    if sunset <= sunrise:
        return None
    tw = max(60.0, twilight_seconds)
    t0 = sunrise - tw
    t1 = sunrise + tw
    t2 = sunset - tw
    t3 = sunset + tw

    if t1 <= now_ts <= t2:
        return 1.0
    if t0 <= now_ts < t1:
        return _clamp((now_ts - t0) / (t1 - t0), 0.0, 1.0)
    if t2 < now_ts <= t3:
        return _clamp(1.0 - (now_ts - t2) / (t3 - t2), 0.0, 1.0)
    return 0.0


def day_phase_fallback(weather: Dict[str, Any]) -> float:
    """Repli sans sunrise/sunset : suffixe icône OWM puis heure locale."""
    icon = weather.get("icon") or ""
    if len(icon) >= 1:
        suf = icon[-1]
        if suf == "n":
            return 0.12
        if suf == "d":
            return 0.92
    try:
        h = int(weather.get("hour", 12))
    except (TypeError, ValueError):
        h = 12
    if 6 <= h < 20:
        return 0.85
    return 0.15


def resolve_ambient_background(
    weather: Dict[str, Any],
    config: Dict[str, Any],
    *,
    now_ts: Optional[float] = None,
) -> Optional[Tuple[Tuple[int, int, int], int]]:
    """
    Retourne (fill_rgb, alpha_255) pour le composite sous / sur le fond photo,
    ou None si l'ambiance dynamique est désactivée.
    """
    if not config.get("use_ambient_weather_background"):
        return None

    if now_ts is None:
        now_ts = datetime.now(timezone.utc).timestamp()

    twilight_min = float(config.get("ambient_twilight_minutes", 45))
    twilight_sec = max(60.0, twilight_min * 60.0)

    sunrise = weather.get("sunrise")
    sunset = weather.get("sunset")
    if sunrise is not None and not isinstance(sunrise, int):
        try:
            sunrise = int(sunrise)
        except (TypeError, ValueError):
            sunrise = None
    if sunset is not None and not isinstance(sunset, int):
        try:
            sunset = int(sunset)
        except (TypeError, ValueError):
            sunset = None

    phase = day_phase_from_sun_times(sunrise, sunset, now_ts, twilight_sec)
    if phase is None:
        phase = day_phase_fallback(weather)
    else:
        phase = float(phase)

    phase = _clamp(phase, 0.0, 1.0)

    try:
        clouds = int(weather.get("clouds", 0))
    except (TypeError, ValueError):
        clouds = 0
    clouds = max(0, min(100, clouds))
    clear_w = (100 - clouds) / 100.0

    min_day = float(config.get("ambient_min_day_brightness", 0.22))
    min_day = _clamp(min_day, 0.0, 1.0)
    day_brightness = phase * (min_day + (1.0 - min_day) * clear_w)

    night_rgb = _rgb_from_config(config, "ambient_night_bg", (10, 12, 20))
    day_clear_rgb = _rgb_from_config(config, "ambient_day_clear_bg", (248, 250, 255))
    day_overcast_rgb = _rgb_from_config(config, "ambient_day_overcast_bg", (152, 158, 168))

    fill_base = _lerp_rgb(night_rgb, day_clear_rgb, day_brightness)
    overcast_mix = (clouds / 100.0) * phase
    fill_rgb = _lerp_rgb(fill_base, day_overcast_rgb, overcast_mix)

    base_255 = weather_background_alpha_base_255(config)
    # Nuit / nuages : réduire l'opacité de la photo pour laisser le fill dominer.
    alpha_mult = max(0.14, 0.18 + 0.82 * day_brightness) * (0.48 + 0.52 * clear_w)
    alpha_255 = int(round(base_255 * alpha_mult))
    alpha_255 = max(0, min(255, alpha_255))

    return (fill_rgb, alpha_255)

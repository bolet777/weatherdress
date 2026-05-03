"""Cycles synthetic weather + outfit scenarios for visual QA without the weather API."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from . import outfit


def _w(
    *,
    temp: float,
    rain: float = 0,
    snow: float = 0,
    clouds: int = 50,
    wind_kmh: float = 10,
    hour: int = 12,
    description: str = "",
    icon: str = "02d",
    condition_id: int = 801,
) -> Dict[str, Any]:
    return {
        "temp": temp,
        "rain": rain,
        "snow": snow,
        "clouds": clouds,
        "wind_kmh": wind_kmh,
        "hour": hour,
        "description": description,
        "icon": icon,
        "condition_id": condition_id,
    }


# Each entry: label for the window caption, current weather, optional forecast slices.
SCENARIOS: List[Dict[str, Any]] = [
    {
        "label": "Heavy rain + cold (umbrella, rain_boots)",
        "weather": _w(
            temp=6,
            rain=8,
            clouds=92,
            wind_kmh=12,
            hour=14,
            description="Pluie forte",
            icon="10d",
            condition_id=502,
        ),
        "forecast": [],
    },
    {
        "label": "Snow + freezing (boots, scarf)",
        "weather": _w(
            temp=-7,
            snow=1.5,
            clouds=85,
            wind_kmh=8,
            hour=11,
            description="Neige",
            icon="13d",
            condition_id=601,
        ),
        "forecast": [],
    },
    {
        "label": "Ice — cold rain + freezing rain id (crampons)",
        "weather": _w(
            temp=0,
            rain=0.8,
            snow=0,
            clouds=95,
            wind_kmh=14,
            hour=8,
            description="Pluie verglaçante",
            icon="13d",
            condition_id=511,
        ),
        "forecast": [],
    },
    {
        "label": "Full sun midday — hot (sun_screen, cap)",
        "weather": _w(
            temp=26,
            clouds=10,
            wind_kmh=6,
            hour=12,
            description="Ensoleillé",
            icon="01d",
            condition_id=800,
        ),
        "forecast": [],
    },
    {
        "label": "Partly cloudy — sunglasses",
        "weather": _w(
            temp=22,
            clouds=25,
            wind_kmh=5,
            hour=12,
            description="Partiellement nuageux",
            icon="02d",
            condition_id=801,
        ),
        "forecast": [],
    },
    {
        "label": "Strong wind + cold (scarf)",
        "weather": _w(
            temp=7,
            clouds=55,
            wind_kmh=38,
            hour=15,
            description="Venteux",
            icon="04d",
            condition_id=804,
        ),
        "forecast": [],
    },
    {
        "label": "Mild cloudy — no accessories",
        "weather": _w(
            temp=20,
            clouds=72,
            wind_kmh=8,
            hour=14,
            description="Nuageux",
            icon="03d",
            condition_id=802,
        ),
        "forecast": [],
    },
    {
        "label": "Extreme cold (verycold → cold sprite)",
        "weather": _w(
            temp=-16,
            clouds=45,
            wind_kmh=10,
            hour=12,
            description="Très froid",
            icon="02d",
            condition_id=802,
        ),
        "forecast": [],
    },
    {
        "label": "Extreme heat (veryhot)",
        "weather": _w(
            temp=36,
            clouds=6,
            wind_kmh=4,
            hour=14,
            description="Canicule",
            icon="01d",
            condition_id=800,
        ),
        "forecast": [],
    },
    {
        "label": "Rain at night — umbrella only",
        "weather": _w(
            temp=11,
            rain=2.5,
            clouds=100,
            wind_kmh=14,
            hour=22,
            description="Pluie",
            icon="10n",
            condition_id=500,
        ),
        "forecast": [],
    },
    {
        "label": "Forecast — clear then rain (future umbrella)",
        "weather": _w(
            temp=22,
            clouds=55,
            wind_kmh=9,
            hour=12,
            description="Nuages épars",
            icon="03d",
            condition_id=802,
        ),
        "forecast": [
            {
                "hour": 15,
                "hours_from_now": 3,
                "temp": 17,
                "description": "Pluie",
                "icon": "10d",
                "wind_kmh": 12,
                "rain": 2,
                "snow": 0,
                "clouds": 80,
            },
        ],
    },
    {
        "label": "Hot night — hat (cap/sun rules off)",
        "weather": _w(
            temp=31,
            clouds=12,
            wind_kmh=6,
            hour=21,
            description="Clair",
            icon="01n",
            condition_id=800,
        ),
        "forecast": [],
    },
]


class DebugPreview:
    """Advances through ``SCENARIOS`` every ``debug_preview_interval_seconds``."""

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        cfg = config or {}
        raw = cfg.get("debug_preview_interval_seconds", 5)
        try:
            self._interval = max(0.5, float(raw))
        except (TypeError, ValueError):
            self._interval = 5.0
        self._idx = 0
        self._last_switch: Optional[float] = None

    def next_frame(self, now: float, gender: str, number: int) -> Dict[str, Any]:
        """
        Return ``label``, ``weather``, and ``outfit`` for the active scenario.

        ``gender`` and ``number`` are passed through to ``get_outfit_with_identity``.
        """
        if self._last_switch is None:
            self._last_switch = now
        elif now - self._last_switch >= self._interval:
            self._idx = (self._idx + 1) % len(SCENARIOS)
            self._last_switch = now

        scen = SCENARIOS[self._idx]
        weather = scen["weather"]
        forecast: List[Dict[str, Any]] = scen.get("forecast") or []
        outfit_dict = outfit.get_outfit_with_identity(weather, forecast, gender, number)
        return {
            "label": scen["label"],
            "weather": weather,
            "outfit": outfit_dict,
        }

"""Tests mapping icônes météo (OpenWeather condition id)."""

import os

import weatherdress.weather_icons as wi


def _images_root():
    return os.path.join(os.path.dirname(os.path.dirname(__file__)), "images")


def test_resolve_thunderstorm():
    fn, fb = wi.resolve_weather_icon_filename(201)
    assert fn == "thunder.png" and not fb


def test_resolve_freezing_rain():
    fn, fb = wi.resolve_weather_icon_filename(511)
    assert fn == "sleet.png" and not fb


def test_resolve_heavy_shower_vs_light():
    h, fb = wi.resolve_weather_icon_filename(522)
    assert h == "heavy-rain.png" and not fb
    lite, fb2 = wi.resolve_weather_icon_filename(500)
    assert lite == "rainy.png" and not fb2


def test_resolve_clear_day_night():
    d, fb = wi.resolve_weather_icon_filename(800, "01d")
    assert d == "sunny.png" and not fb
    n, fb2 = wi.resolve_weather_icon_filename(800, "01n")
    assert n == "night-clear.png" and not fb2


def test_resolve_fallback_sand():
    fn, fb = wi.resolve_weather_icon_filename(751)
    assert fn == wi.FALLBACK_FILENAME and fb


def test_get_weather_icon_path_exists():
    p = wi.get_weather_icon_path(
        _images_root(),
        500,
        "10d",
    )
    assert p and os.path.isfile(p)

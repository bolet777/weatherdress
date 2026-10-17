import os
from datetime import date

import weatherdress.background_assets as background_assets


_JULY = date(2026, 7, 15)


def _map_path():
    root = os.path.dirname(os.path.dirname(__file__))
    return os.path.join(root, "images", "backgrounds")


def test_load_background_map_reads_project_file():
    data = background_assets.load_background_map(_map_path())
    assert data is not None
    assert "keys_to_file" in data
    assert "rules" in data
    assert data["keys_to_file"]["rain"] == "rain.png"


def test_resolve_key_thunderstorm():
    m = background_assets.load_background_map(_map_path())
    w = {"condition_id": 201, "icon": "11d"}
    assert background_assets.resolve_background_key(w, m, _JULY) == "thunderstorm"


def test_resolve_key_rain():
    m = background_assets.load_background_map(_map_path())
    w = {"condition_id": 501, "icon": "10d"}
    assert background_assets.resolve_background_key(w, m, _JULY) == "rain"


def test_resolve_key_clear_day_vs_night():
    m = background_assets.load_background_map(_map_path())
    assert (
        background_assets.resolve_background_key(
            {"condition_id": 800, "icon": "01d"}, m, _JULY
        )
        == "sunny"
    )
    assert (
        background_assets.resolve_background_key(
            {"condition_id": 800, "icon": "01n"}, m, _JULY
        )
        == "sunny_night"
    )
    assert (
        background_assets.resolve_background_key(
            {"condition_id": 800, "icon": "01"}, m, _JULY
        )
        == "sunny"
    )


def test_resolve_key_winter_variants():
    m = background_assets.load_background_map(_map_path())
    january = date(2026, 1, 15)
    assert (
        background_assets.resolve_background_key(
            {"condition_id": 800, "icon": "01d"}, m, january
        )
        == "sunny_winter"
    )
    assert (
        background_assets.resolve_background_key(
            {"condition_id": 800, "icon": "01n"}, m, january
        )
        == "sunny_winter_night"
    )
    assert (
        background_assets.resolve_background_key(
            {"condition_id": 500, "icon": "10n"}, m, january
        )
        == "rain_night"
    )
    assert (
        background_assets.resolve_background_key(
            {"condition_id": 800, "icon": "01d"}, m, _JULY
        )
        == "sunny"
    )


def test_resolve_key_winter_night_without_winter_night_key():
    m = {
        "default_key": "partly_cloudy",
        "keys_to_file": {
            "sunny": "sunny.png",
            "sunny_night": "sunny_night.png",
            "sunny_winter": "sunny_winter.png",
        },
        "rules": [{"condition_id": 800, "key": "sunny"}],
    }
    assert (
        background_assets.resolve_background_key(
            {"condition_id": 800, "icon": "01n"}, m, date(2026, 1, 15)
        )
        == "sunny_night"
    )


def test_resolve_key_rain_night():
    m = background_assets.load_background_map(_map_path())
    w = {"condition_id": 500, "icon": "10n"}
    assert background_assets.resolve_background_key(w, m, _JULY) == "rain_night"


def test_resolve_key_fog_day():
    m = background_assets.load_background_map(_map_path())
    w = {"condition_id": 741, "icon": "50d"}
    assert background_assets.resolve_background_key(w, m, _JULY) == "fog"


def test_resolve_key_night_falls_back_to_day_key():
    m = {
        "default_key": "partly_cloudy",
        "keys_to_file": {"rain": "rain.png"},
        "rules": [{"condition_id": 500, "key": "rain"}],
    }
    w = {"condition_id": 500, "icon": "10n"}
    assert background_assets.resolve_background_key(w, m, _JULY) == "rain"


def test_resolve_key_dust_before_atmosphere_range():
    m = background_assets.load_background_map(_map_path())
    w = {"condition_id": 761, "icon": "50d"}
    assert background_assets.resolve_background_key(w, m, _JULY) == "dust"


def test_resolve_image_path_exists():
    m = background_assets.load_background_map(_map_path())
    root = os.path.dirname(os.path.dirname(__file__))
    images_dir = os.path.join(root, "images")
    w = {"condition_id": 500, "icon": "10d"}
    p = background_assets.resolve_background_image_path(images_dir, w, m)
    assert p is not None
    assert os.path.isfile(p)

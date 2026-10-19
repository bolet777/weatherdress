import json

import pytest

import weatherdress.config_file as config_file
import weatherdress.layout_config as layout_config

ROOT_DEFAULT = config_file.DEFAULT_CONFIG_PATH


def test_default_file_covers_layout_and_app_keys():
    data = json.loads(ROOT_DEFAULT.read_text(encoding="utf-8"))
    assert set(data["layout"]) == set(layout_config.DEFAULT_LAYOUT)
    assert set(data["accessories_column"]) == {"plate_color", "track_color"}
    assert set(data["transit"]) == {
        "stm_api_key",
        "gtfs_url",
        "bus_stops",
        "metro_station",
        "metro_route_id",
        "metro_line_color",
        "metro_directions",
        "transit_refresh_seconds",
        "transit_alternate_seconds",
        "card_title_font_px",
        "card_subtitle_font_px",
        "card_times_font_px",
        "strip_mode_letter_font_px",
        "card_height_px",
    }
    assert data["transit"]["card_height_px"] is None
    for key in (
        "api_key",
        "city",
        "language",
        "units",
        "fullscreen",
        "use_weather_background",
        "weather_background_alpha",
        "use_ambient_weather_background",
        "ambient_twilight_minutes",
        "ambient_min_day_brightness",
        "ambient_night_bg",
        "ambient_day_clear_bg",
        "ambient_day_overcast_bg",
        "character_colorkey",
        "background_color",
        "circle_background_color",
        "screen_width",
        "screen_height",
        "refresh_minutes",
        "forecast_hours",
        "identity_on_each_refresh",
        "character_variant_max",
        "debug_preview",
        "debug_preview_interval_seconds",
    ):
        assert key in data
    assert data["api_key"] == "VOTRE_CLE_OPENWEATHERMAP_ICI"
    assert data["transit"]["stm_api_key"] == "VOTRE_CLE_API_STM_ICI"


def test_merge_nested_objects_and_replaces_data_dicts():
    base = {
        "city": "Montreal,CA",
        "layout": {"weather_mode": "after_character", "weather_gap_after_character_px": 12},
        "accessories_column": {"plate_color": [1, 2, 3, 4], "track_color": [5, 6, 7, 8]},
        "transit": {
            "stm_api_key": "placeholder",
            "metro_station": "Outremont",
            "bus_stops": {"56220": "Snowdon", "56221": "St-Michel"},
            "metro_directions": {"Snowdon": "Snowdon", "Saint-Michel": "St-Michel"},
        },
    }
    override = {
        "layout": {"weather_gap_after_character_px": 40},
        "accessories_column": {"plate_color": [9, 9, 9, 9]},
        "transit": {
            "stm_api_key": "secret",
            "bus_stops": {"1": "Seul"},
        },
    }
    merged = config_file.merge_config(base, override)
    assert merged["city"] == "Montreal,CA"
    assert merged["layout"] == {
        "weather_mode": "after_character",
        "weather_gap_after_character_px": 40,
    }
    assert merged["accessories_column"]["plate_color"] == [9, 9, 9, 9]
    assert merged["accessories_column"]["track_color"] == [5, 6, 7, 8]
    assert merged["transit"]["stm_api_key"] == "secret"
    assert merged["transit"]["metro_station"] == "Outremont"
    assert merged["transit"]["bus_stops"] == {"1": "Seul"}
    assert merged["transit"]["metro_directions"] == {
        "Snowdon": "Snowdon",
        "Saint-Michel": "St-Michel",
    }
    assert base["layout"]["weather_gap_after_character_px"] == 12
    assert config_file.overrides_only(base, merged) == override


def test_override_of_whole_direction_map_is_not_merged():
    base = {"transit": {"metro_directions": {"Snowdon": "Snowdon", "Saint-Michel": "St-Michel"}}}
    override = {"transit": {"metro_directions": {"Snowdon": "Autre"}}}
    merged = config_file.merge_config(base, override)
    assert merged["transit"]["metro_directions"] == {"Snowdon": "Autre"}
    assert config_file.overrides_only(base, merged) == override


def test_load_config_without_user_file(tmp_path, monkeypatch):
    defaults = {"city": "Montreal,CA", "layout": {"weather_mode": "after_character"}}
    default_path = tmp_path / "config.default.json"
    default_path.write_text(json.dumps(defaults), encoding="utf-8")
    monkeypatch.setattr(config_file, "DEFAULT_CONFIG_PATH", default_path)
    monkeypatch.setattr(config_file, "CONFIG_PATH", tmp_path / "config.json")
    assert config_file.load_config() == defaults


def test_load_config_merges_user_file(tmp_path, monkeypatch):
    defaults = {
        "city": "Montreal,CA",
        "refresh_minutes": 5,
        "transit": {"bus_stops": {"1": "A", "2": "B"}, "metro_station": "Outremont"},
    }
    user = {"refresh_minutes": 15, "transit": {"bus_stops": {"9": "Z"}}}
    default_path = tmp_path / "config.default.json"
    user_path = tmp_path / "config.json"
    default_path.write_text(json.dumps(defaults), encoding="utf-8")
    user_path.write_text(json.dumps(user), encoding="utf-8")
    monkeypatch.setattr(config_file, "DEFAULT_CONFIG_PATH", default_path)
    monkeypatch.setattr(config_file, "CONFIG_PATH", user_path)
    loaded = config_file.load_config()
    assert loaded["city"] == "Montreal,CA"
    assert loaded["refresh_minutes"] == 15
    assert loaded["transit"]["bus_stops"] == {"9": "Z"}
    assert loaded["transit"]["metro_station"] == "Outremont"


def test_load_config_rejects_invalid_user_json(tmp_path, monkeypatch, capsys):
    default_path = tmp_path / "config.default.json"
    user_path = tmp_path / "config.json"
    default_path.write_text('{"city": "Montreal,CA"}\n', encoding="utf-8")
    user_path.write_text("{", encoding="utf-8")
    monkeypatch.setattr(config_file, "DEFAULT_CONFIG_PATH", default_path)
    monkeypatch.setattr(config_file, "CONFIG_PATH", user_path)
    with pytest.raises(SystemExit):
        config_file.load_config()
    assert "JSON valide" in capsys.readouterr().out

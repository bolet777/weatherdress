from weatherdress.outfit import (
    active_accessories,
    character_type,
    get_outfit_with_identity,
    pick_identity,
)


def test_character_type_snow():
    assert character_type(5, snow=0.5) == "snow"


def test_character_type_veryhot():
    assert character_type(30, snow=0) == "veryhot"


def test_character_type_hot():
    assert character_type(26, snow=0) == "hot"


def test_character_type_normal():
    assert character_type(20, snow=0) == "normal"


def test_character_type_cold():
    assert character_type(0, snow=0) == "cold"


def test_character_type_verycold():
    assert character_type(-15, snow=0) == "verycold"


def test_accessories_rain():
    w = {"rain": 1, "snow": 0, "wind_kmh": 10, "clouds": 80, "hour": 12, "temp": 15}
    assert "umbrella" in active_accessories(w)


def test_accessories_sunglasses():
    # clouds 25: sunglasses (partly cloudy) but not sun_screen (needs clouds < 20)
    w = {"rain": 0, "snow": 0, "wind_kmh": 5, "clouds": 25, "hour": 12, "temp": 22}
    assert "sunglasses" in active_accessories(w)


def test_accessories_scarf_cold():
    w = {"rain": 0, "snow": 0, "wind_kmh": 5, "clouds": 50, "hour": 9, "temp": 2}
    assert "scarf" in active_accessories(w)


def test_accessories_scarf_wind():
    w = {"rain": 0, "snow": 0, "wind_kmh": 35, "clouds": 50, "hour": 9, "temp": 15}
    assert "scarf" in active_accessories(w)


def test_accessories_feet_snow_boots_not_rain_boots():
    w = {
        "rain": 0,
        "snow": 1,
        "wind_kmh": 8,
        "clouds": 80,
        "hour": 11,
        "temp": -5,
    }
    acc = active_accessories(w)
    assert "boots" in acc
    assert "rain_boots" not in acc


def test_accessories_feet_heavy_rain_rain_boots_not_snow_boots():
    w = {
        "rain": 8,
        "snow": 0,
        "wind_kmh": 12,
        "clouds": 90,
        "hour": 14,
        "temp": 6,
    }
    acc = active_accessories(w)
    assert "rain_boots" in acc
    assert "boots" not in acc


def test_accessories_crampons_cold_rain_no_snow():
    w = {
        "rain": 0.5,
        "snow": 0,
        "wind_kmh": 10,
        "clouds": 90,
        "hour": 10,
        "temp": 1,
    }
    acc = active_accessories(w)
    assert "crampons" in acc
    assert "boots" not in acc


def test_accessories_crampons_freezing_rain_condition_id():
    w = {
        "rain": 0,
        "snow": 0,
        "wind_kmh": 12,
        "clouds": 100,
        "hour": 7,
        "temp": -2,
        "condition_id": 511,
    }
    acc = active_accessories(w)
    assert "crampons" in acc


def test_accessories_crampons_condition_id_511_coerces_string():
    w = {
        "rain": 0,
        "snow": 0,
        "wind_kmh": 10,
        "clouds": 100,
        "hour": 8,
        "temp": -1,
        "condition_id": "511",
    }
    assert "crampons" in active_accessories(w)


def test_accessories_crampons_511_even_if_trace_snow_reported():
    """OWM peut remplir `snow` lors de brouillas / mélange alors que id = 511."""
    w = {
        "rain": 0,
        "snow": 0.2,
        "wind_kmh": 15,
        "clouds": 100,
        "hour": 9,
        "temp": -1,
        "condition_id": 511,
    }
    acc = active_accessories(w)
    assert "crampons" in acc
    assert "boots" in acc


def test_accessories_no_crampons_when_snow_use_boots():
    w = {
        "rain": 0,
        "snow": 1,
        "wind_kmh": 8,
        "clouds": 80,
        "hour": 11,
        "temp": -5,
    }
    acc = active_accessories(w)
    assert "boots" in acc
    assert "crampons" not in acc


def test_get_outfit_verycold_uses_cold_sprite_prefix():
    current = {
        "temp": -15,
        "snow": 0,
        "rain": 0,
        "wind_kmh": 5,
        "clouds": 50,
        "hour": 12,
    }
    r = get_outfit_with_identity(current, [], "man", 2)
    assert r["character"] == "cold_man2"


def test_get_outfit_veryhot_uses_hot_sprite_prefix():
    current = {
        "temp": 30,
        "snow": 0,
        "rain": 0,
        "wind_kmh": 5,
        "clouds": 50,
        "hour": 12,
    }
    r = get_outfit_with_identity(current, [], "woman", 1)
    assert r["character"] == "hot_woman1"


def test_pick_identity_respects_character_variant_max():
    for _ in range(50):
        _, n = pick_identity({"character_variant_max": 3})
        assert 1 <= n <= 3


def test_get_outfit_with_identity_structure():
    current = {"temp": 20, "snow": 0, "rain": 0, "wind_kmh": 10, "clouds": 20, "hour": 12}
    forecast = [
        {
            "temp": 18,
            "snow": 0,
            "rain": 2,
            "wind_kmh": 10,
            "clouds": 60,
            "hour": 15,
            "hours_from_now": 3,
        },
    ]
    result = get_outfit_with_identity(current, forecast, "woman", 1)
    assert result["character"] == "normal_woman1"
    assert isinstance(result["current_accessories"], list)
    assert isinstance(result["future_accessories"], list)
    # umbrella est futur donc pas dans current
    assert "umbrella" not in result["current_accessories"]
    future_names = [f["accessory"] for f in result["future_accessories"]]
    assert "umbrella" in future_names
    u = next(f for f in result["future_accessories"] if f["accessory"] == "umbrella")
    assert u["hour"] == 15
    assert u["hours_from_now"] == 3

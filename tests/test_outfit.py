from outfit import character_type, active_accessories, get_outfit_with_identity, pick_identity


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
    w = {"rain": 0, "snow": 0, "wind_kmh": 5, "clouds": 10, "hour": 12, "temp": 22}
    assert "sunglasses" in active_accessories(w)


def test_accessories_scarf_cold():
    w = {"rain": 0, "snow": 0, "wind_kmh": 5, "clouds": 50, "hour": 9, "temp": 2}
    assert "scarf" in active_accessories(w)


def test_accessories_scarf_wind():
    w = {"rain": 0, "snow": 0, "wind_kmh": 35, "clouds": 50, "hour": 9, "temp": 15}
    assert "scarf" in active_accessories(w)


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
        {"temp": 18, "snow": 0, "rain": 2, "wind_kmh": 10, "clouds": 60, "hour": 15},
    ]
    result = get_outfit_with_identity(current, forecast, "woman", 1)
    assert result["character"] == "normal_woman1"
    assert isinstance(result["current_accessories"], list)
    assert isinstance(result["future_accessories"], list)
    # umbrella est futur donc pas dans current
    assert "umbrella" not in result["current_accessories"]
    future_names = [f["accessory"] for f in result["future_accessories"]]
    assert "umbrella" in future_names

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
    w = {"rain": 0, "snow": 0, "wind_kmh": 5, "clouds": 25, "hour": 12, "temp": 22}
    assert "sunglasses" in active_accessories(w)


def test_accessories_sunglasses_clear_sky_alongside_sun_screen():
    """sun_screen n'a plus de slot : lunettes + écran solaire si ciel clair le jour."""
    w = {
        "rain": 0,
        "snow": 0,
        "wind_kmh": 5,
        "clouds": 10,
        "hour": 12,
        "temp": 24,
    }
    acc = active_accessories(w)
    assert "sunglasses" in acc
    assert "sun_screen" in acc


def test_accessories_sunglasses_heatwave_high_clouds():
    w = {
        "rain": 0,
        "snow": 0,
        "wind_kmh": 8,
        "clouds": 95,
        "hour": 15,
        "temp": 34,
    }
    assert "sunglasses" in active_accessories(w)


def test_accessories_sunglasses_not_at_night_by_hour():
    w = {
        "rain": 0,
        "snow": 0,
        "wind_kmh": 5,
        "clouds": 15,
        "hour": 22,
        "temp": 22,
    }
    assert "sunglasses" not in active_accessories(w)


def test_accessories_sunglasses_not_at_night_by_sun_times():
    w = {
        "rain": 0,
        "snow": 0,
        "wind_kmh": 5,
        "clouds": 10,
        "hour": 12,
        "temp": 25,
        "sunrise": 1_000_000,
        "sunset": 1_000_100,
        "now_ts": 1_000_200,
    }
    assert "sunglasses" not in active_accessories(w)


def test_accessories_beanie_snow():
    w = {"rain": 0, "snow": 1, "wind_kmh": 8, "clouds": 90, "hour": 11, "temp": -2}
    assert "beanie" in active_accessories(w)


def test_accessories_beanie_frigid_no_snow():
    w = {"rain": 0, "snow": 0, "wind_kmh": 10, "clouds": 50, "hour": 12, "temp": 4}
    acc = active_accessories(w)
    assert "beanie" in acc
    assert "cap" not in acc


def test_accessories_cap_mild_sunny_not_hot():
    # Nuages 20–29 : casquette, pas chapeau soleil (nuages ≥ 20)
    w = {"rain": 0, "snow": 0, "wind_kmh": 6, "clouds": 25, "hour": 12, "temp": 22}
    acc = active_accessories(w)
    assert "cap" in acc
    assert "hat" not in acc
    assert "beanie" not in acc


def test_accessories_hat_hot_beats_cap():
    w = {"rain": 0, "snow": 0, "wind_kmh": 4, "clouds": 8, "hour": 14, "temp": 33}
    acc = active_accessories(w)
    assert "hat" in acc
    assert "cap" not in acc


def test_accessories_hat_clear_daytime():
    w = {"rain": 0, "snow": 0, "wind_kmh": 5, "clouds": 15, "hour": 10, "temp": 18}
    acc = active_accessories(w)
    assert "hat" in acc
    assert "beanie" not in acc


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


def test_pick_identity_respects_character_variant_max_clip(tmp_path):
    d = tmp_path / "ch"
    d.mkdir()
    for g in ("woman", "man"):
        for n in (1, 2, 3, 4):
            (d / f"normal_{g}{n}.png").write_bytes(b"")
    weather = {"temp": 20, "snow": 0}
    for _ in range(40):
        _, n = pick_identity(
            {"character_variant_max": 2}, str(d), weather
        )
        assert n in (1, 2)


def test_pick_identity_chooses_only_existing_variants(tmp_path):
    d = tmp_path / "ch"
    d.mkdir()
    for g in ("man", "woman"):
        for n in (1, 3, 6):
            (d / f"hot_{g}{n}.png").write_bytes(b"")
    weather = {"temp": 30, "snow": 0}
    seen = set()
    for _ in range(80):
        g, n = pick_identity({}, str(d), weather)
        assert n in (1, 3, 6)
        seen.add((g, n))
    assert len(seen) >= 4


def test_pick_identity_fallback_when_no_matching_files(tmp_path):
    d = tmp_path / "empty"
    d.mkdir()
    weather = {"temp": 20, "snow": 0}
    for _ in range(20):
        _, n = pick_identity({"character_variant_max": 3}, str(d), weather)
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

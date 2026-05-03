import weatherdress.ambient_background as amb


def _cfg_ambient_on():
    return {
        "use_ambient_weather_background": True,
        "weather_background_alpha": 1.0,
    }


def test_resolve_returns_none_when_disabled():
    w = {"sunrise": 10000, "sunset": 20000, "clouds": 0, "icon": "01d", "hour": 12}
    assert amb.resolve_ambient_background(w, {}) is None
    assert amb.resolve_ambient_background(w, {"use_ambient_weather_background": False}) is None


def test_day_phase_full_day_between_transitions():
    # sunrise=10000, sunset=20000, tw=600 -> plateau entre t1=10600 et t2=19400
    assert amb.day_phase_from_sun_times(10000, 20000, 15000, 600) == 1.0


def test_day_phase_midnight_before_dawn():
    assert amb.day_phase_from_sun_times(10000, 20000, 5000, 600) == 0.0


def test_day_phase_invalid_returns_none():
    assert amb.day_phase_from_sun_times(None, 20000, 15000, 600) is None
    assert amb.day_phase_from_sun_times(10000, None, 15000, 600) is None
    assert amb.day_phase_from_sun_times(20000, 10000, 15000, 600) is None


def test_fallback_icon_n_vs_d():
    assert amb.day_phase_fallback({"icon": "02n", "hour": 12}) == 0.12
    assert amb.day_phase_fallback({"icon": "02d", "hour": 2}) == 0.92


def test_fallback_hour_when_no_icon_suffix():
    assert amb.day_phase_fallback({"icon": "x", "hour": 10}) == 0.85
    assert amb.day_phase_fallback({"icon": "x", "hour": 22}) == 0.15


def test_ambient_noon_clear_brighter_than_night():
    cfg = _cfg_ambient_on()
    w = {"sunrise": 10000, "sunset": 20000, "clouds": 0, "icon": "01d", "hour": 12}
    fill_day, alpha_day = amb.resolve_ambient_background(w, cfg, now_ts=15000)
    fill_night, alpha_night = amb.resolve_ambient_background(w, cfg, now_ts=5000)
    assert sum(fill_day) > sum(fill_night)
    assert alpha_day >= alpha_night


def test_ambient_heavy_clouds_darkens_vs_clear():
    cfg = _cfg_ambient_on()
    base = {"sunrise": 10000, "sunset": 20000, "icon": "04d", "hour": 14}
    fill_clear, _ = amb.resolve_ambient_background(
        {**base, "clouds": 0}, cfg, now_ts=15000
    )
    fill_cloud, _ = amb.resolve_ambient_background(
        {**base, "clouds": 100}, cfg, now_ts=15000
    )
    assert sum(fill_clear) > sum(fill_cloud)


def test_fallback_without_sun_still_resolves():
    cfg = _cfg_ambient_on()
    w = {"clouds": 40, "icon": "10n", "hour": 23}
    r = amb.resolve_ambient_background(w, cfg, now_ts=1_700_000_000)
    assert r is not None
    fill, alpha = r
    assert len(fill) == 3
    assert 0 <= alpha <= 255


def test_weather_background_alpha_base_respects_config():
    cfg = _cfg_ambient_on()
    cfg["weather_background_alpha"] = 0.5
    assert amb.weather_background_alpha_base_255(cfg) == 128

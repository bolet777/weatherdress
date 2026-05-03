"""Smoke tests for synthetic debug / preview cycling."""

from weatherdress.debug_preview import DebugPreview, SCENARIOS


def test_debug_preview_next_frame_no_crash():
    cfg = {"debug_preview_interval_seconds": 5}
    dp = DebugPreview(cfg)
    f0 = dp.next_frame(0.0, "woman", 1)
    assert f0["label"]
    assert f0["weather"]["temp"] is not None
    assert f0["outfit"]["character"]
    assert isinstance(f0["outfit"]["current_accessories"], list)

    f1 = dp.next_frame(6.0, "man", 2)
    assert f1["label"] != f0["label"] or len(SCENARIOS) == 1

    _ = dp.next_frame(1000.0, "woman", 3)


def test_debug_preview_has_scenario_forecast_umbrella():
    labels = [s["label"] for s in SCENARIOS]
    assert any("Forecast" in L and "umbrella" in L for L in labels)


def test_debug_preview_each_scenario_forecast_has_distinct_hours_from_now():
    """Sinon un mauvais ordre des pastilles futur n’apparaîtrait pas aux tests."""
    for scen in SCENARIOS:
        fc = scen.get("forecast") or []
        hours = [x.get("hours_from_now") for x in fc]
        assert len(set(hours)) >= 2, (scen.get("label"), hours)


def test_debug_preview_each_scenario_has_at_least_two_future_accessories():
    from weatherdress.outfit import get_outfit_with_identity

    for scen in SCENARIOS:
        o = get_outfit_with_identity(
            scen["weather"],
            scen.get("forecast") or [],
            "woman",
            1,
        )
        assert len(o["future_accessories"]) >= 2, scen.get("label")

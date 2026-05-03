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

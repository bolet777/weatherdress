import weatherdress.layout_config as layout_config


def test_effective_layout_defaults():
    cfg = {}
    L = layout_config.effective_layout(cfg)
    assert L["weather_mode"] == "after_character"
    assert L["character_center_x_pct"] == 0.28
    assert L["weather_transit_vertical_offset_px"] == -28


def test_effective_layout_override():
    cfg = {"layout": {"weather_mode": "screen_right", "weather_top_pct": 0.2}}
    L = layout_config.effective_layout(cfg)
    assert L["weather_mode"] == "screen_right"
    assert L["weather_top_pct"] == 0.2
    assert L["character_center_x_pct"] == 0.28

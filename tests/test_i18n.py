import i18n


def test_messages_fr_overrides_en():
    cfg = {"language": "fr"}
    m = i18n.messages(cfg)
    assert m["weather_loading"] == "Chargement météo…"
    assert m["window_title"] == "WeatherDress"


def test_messages_en():
    cfg = {"language": "en"}
    m = i18n.messages(cfg)
    assert m["weather_loading"] == "Loading weather…"


def test_messages_default_without_language_key_is_french():
    cfg = {}
    m = i18n.messages(cfg)
    assert m["weather_loading"] == "Chargement météo…"
    assert i18n.effective_language(cfg) == "fr"


def test_substitute_weather_bar():
    cfg = {"language": "fr"}
    line = i18n.substitute(
        cfg,
        "weather_bar",
        temp="12°C",
        description="ciel dégagé",
    )
    assert "12°C" in line
    assert "ciel dégagé" in line


def test_substitute_braces_in_description_unchanged_as_literal():
    cfg = {"language": "en"}
    line = i18n.substitute(
        cfg,
        "weather_bar",
        temp="1°F",
        description="weird {not a placeholder} sky",
    )
    assert "{not a placeholder}" in line

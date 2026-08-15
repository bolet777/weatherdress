import datetime

from weatherdress.transit import (
    resolve_stm_api_key,
    transit_config_enabled,
    weekday_column_for_date,
)


def test_weekday_column_monday():
    d = datetime.date(2026, 4, 27)  # lundi
    assert weekday_column_for_date(d) == "monday"


def test_weekday_column_sunday():
    d = datetime.date(2026, 4, 26)  # dimanche
    assert weekday_column_for_date(d) == "sunday"


def test_transit_config_enabled_requires_keys():
    assert not transit_config_enabled({})
    assert not transit_config_enabled({"transit": {}})
    assert not transit_config_enabled({"transit": {"gtfs_url": "http://x"}})
    assert not transit_config_enabled(
        {
            "transit": {
                "gtfs_url": "https://example.com/gtfs.zip",
                "metro_station": "Outremont",
            }
        }
    )
    assert transit_config_enabled(
        {
            "transit": {
                "gtfs_url": "https://example.com/gtfs.zip",
                "metro_station": "Outremont",
                "metro_route_id": "5",
            }
        }
    )


def test_resolve_stm_api_key_from_config():
    key, err = resolve_stm_api_key({"stm_api_key": "abc123"})
    assert key == "abc123"
    assert err is None


def test_resolve_stm_api_key_rejects_placeholder():
    key, err = resolve_stm_api_key({"stm_api_key": "VOTRE_CLE_API_STM_ICI"})
    assert key == ""
    assert err and "placeholder" in err


def test_resolve_stm_api_key_env(monkeypatch):
    monkeypatch.setenv("STM_API_KEY", "from-env")
    key, err = resolve_stm_api_key({"stm_api_key": "ignored"})
    assert key == "from-env"
    assert err is None

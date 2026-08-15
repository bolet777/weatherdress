import datetime
import zipfile
from io import BytesIO

from weatherdress.transit import (
    TransitFetcher,
    merge_transit_display_data,
    resolve_stm_api_key,
    transit_config_enabled,
    transit_placeholder_data,
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


def _sample_transit_config():
    return {
        "transit": {
            "gtfs_url": "https://example.com/gtfs.zip",
            "metro_station": "Outremont",
            "metro_route_id": "5",
            "bus_stops": {"56220": "Snowdon", "56221": "St-Michel"},
            "metro_directions": {
                "Snowdon": "Snowdon",
                "Saint-Michel": "St-Michel",
            },
        }
    }


def test_transit_placeholder_data_from_config():
    cfg = _sample_transit_config()
    ph = transit_placeholder_data(cfg)
    assert set(ph["bus"]) == {"56220", "56221"}
    assert ph["bus"]["56220"]["minutes"] == []
    assert set(ph["metro"]) == {"Snowdon", "Saint-Michel"}


def test_merge_transit_display_data_bus_before_metro_ready():
    cfg = _sample_transit_config()
    live = {
        "bus": {
            "56220": {"route": "51", "label": "Snowdon", "minutes": [3, 12]},
        },
        "metro": {"Snowdon": [5]},
    }
    merged = merge_transit_display_data(cfg, live, metro_ready=False)
    assert merged["bus"]["56220"]["minutes"] == [3, 12]
    assert merged["metro"] == {"Snowdon": [], "Saint-Michel": []}


def test_merge_transit_display_data_metro_when_ready():
    cfg = _sample_transit_config()
    live = {"bus": {}, "metro": {"Snowdon": [5, 11]}}
    merged = merge_transit_display_data(cfg, live, metro_ready=True)
    assert merged["metro"] == {"Snowdon": [5, 11]}


def test_metro_index_cache_roundtrip(tmp_path, monkeypatch):
    gtfs_path = tmp_path / "gtfs.zip"
    cache_path = tmp_path / "metro_index.json"
    buf = BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        z.writestr("stops.txt", "stop_id,stop_name\n1,Outremont\n")
        z.writestr(
            "trips.txt",
            "route_id,service_id,trip_id,trip_headsign\n5,SVC,t1,Snowdon\n",
        )
        z.writestr(
            "stop_times.txt",
            "trip_id,stop_id,departure_time\n"
            "t1,1,10:00:00\n"
            "t1,1,10:05:00\n",
        )
        z.writestr(
            "calendar.txt",
            "service_id,monday,tuesday,wednesday,thursday,friday,saturday,sunday,"
            "start_date,end_date\n"
            "SVC,1,1,1,1,1,1,1,20200101,20991231\n",
        )
    gtfs_path.write_bytes(buf.getvalue())

    cfg = {
        "transit": {
            "gtfs_url": "https://example.com/gtfs.zip",
            "metro_station": "Outremont",
            "metro_route_id": "5",
        }
    }
    monkeypatch.setattr("weatherdress.transit.GTFS_CACHE_PATH", gtfs_path)
    monkeypatch.setattr("weatherdress.transit.METRO_INDEX_CACHE_PATH", cache_path)

    fetcher = TransitFetcher(cfg)
    fetcher._build_metro_index()
    assert len(fetcher._metro_index) == 2
    assert cache_path.is_file()

    fetcher2 = TransitFetcher(cfg)
    assert fetcher2._try_load_metro_index_cache()
    assert len(fetcher2._metro_index) == 2
    assert fetcher2._metro_trips["t1"]["headsign"] == "Snowdon"

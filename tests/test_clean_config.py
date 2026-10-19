import importlib.util
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
_PATH = ROOT / "scripts" / "clean_config.py"


def _load():
    spec = importlib.util.spec_from_file_location("weatherdress_clean_config", _PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


clean = _load()


def test_clean_config_strips_values_equal_to_default(tmp_path, monkeypatch, capsys):
    defaults = {
        "city": "Montreal,CA",
        "fullscreen": True,
        "layout": {"weather_mode": "after_character", "weather_gap_after_character_px": 12},
        "transit": {"bus_stops": {"1": "A", "2": "B"}, "metro_station": "Outremont"},
    }
    user = {
        "city": "Montreal,CA",
        "fullscreen": False,
        "layout": {"weather_mode": "after_character", "weather_gap_after_character_px": 30},
        "transit": {
            "bus_stops": {"1": "A", "2": "B", "3": "C"},
            "metro_station": "Outremont",
        },
    }
    default_path = tmp_path / "config.default.json"
    config_path = tmp_path / "config.json"
    backup_path = tmp_path / "config.json.bak"
    original = json.dumps(user, indent=2) + "\n"
    default_path.write_text(json.dumps(defaults), encoding="utf-8")
    config_path.write_text(original, encoding="utf-8")
    monkeypatch.setattr(clean.config_file, "DEFAULT_CONFIG_PATH", default_path)
    monkeypatch.setattr(clean.config_file, "CONFIG_PATH", config_path)
    monkeypatch.setattr(clean.config_file, "BACKUP_PATH", backup_path)
    assert clean.main() == 0
    assert "nettoyé" in capsys.readouterr().out
    assert json.loads(config_path.read_text(encoding="utf-8")) == {
        "fullscreen": False,
        "layout": {"weather_gap_after_character_px": 30},
        "transit": {"bus_stops": {"1": "A", "2": "B", "3": "C"}},
    }
    assert backup_path.read_text(encoding="utf-8") == original
    assert not list(tmp_path.glob(".config.json.*.tmp"))
    assert clean.main() == 0
    assert "déjà" in capsys.readouterr().out
    assert backup_path.read_text(encoding="utf-8") == original


def test_clean_config_missing_user_file(tmp_path, monkeypatch, capsys):
    default_path = tmp_path / "config.default.json"
    default_path.write_text('{"city": "Montreal,CA"}\n', encoding="utf-8")
    monkeypatch.setattr(clean.config_file, "DEFAULT_CONFIG_PATH", default_path)
    monkeypatch.setattr(clean.config_file, "CONFIG_PATH", tmp_path / "config.json")
    assert clean.main() == 0
    assert "absent" in capsys.readouterr().out

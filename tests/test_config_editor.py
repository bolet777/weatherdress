import base64
import importlib.util
import json
import threading
from http.server import HTTPServer
from pathlib import Path
from urllib.error import HTTPError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

import pytest

ROOT = Path(__file__).resolve().parents[1]
EXAMPLE = ROOT / "config.example.json"
_PATH = ROOT / "scripts" / "config_editor.py"


def _load():
    spec = importlib.util.spec_from_file_location("weatherdress_config_editor", _PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


editor = _load()


def _walk_fields(config, bool_pair=False):
    fields = []

    def walk(obj, prefix):
        for key, value in obj.items():
            path = f"{prefix}.{key}" if prefix else key
            kind = editor.field_kind(path, value)
            if kind == "section":
                walk(value, path)
                continue
            text = editor.format_value(kind, value)
            if bool_pair and kind == "bool":
                fields.append((f"v:{path}", "false"))
                if text == "true":
                    fields.append((f"v:{path}", "true"))
            else:
                fields.append((path if not bool_pair else f"v:{path}", text))

    walk(config, "")
    return fields


def _field_map(config):
    return dict(_walk_fields(config, bool_pair=False))


def test_default_listen_address():
    args = editor.parse_args([])
    assert args.host == "127.0.0.1"
    assert args.port == 8765
    assert editor.HOST == "127.0.0.1"
    assert editor.PORT == 8765


def test_example_roundtrip_preserves_order_and_types():
    original = json.loads(EXAMPLE.read_text(encoding="utf-8"))
    built, errors = editor.build_config(original, _field_map(original))
    assert errors == []
    assert built == original
    assert list(built) == list(original)
    assert list(built["layout"]) == list(original["layout"])
    assert list(built["transit"]) == list(original["transit"])
    assert editor.dump_config(original) == EXAMPLE.read_text(encoding="utf-8")


def test_widget_kinds():
    assert editor.field_kind("api_key", "secret") == "password"
    assert editor.field_kind("transit.stm_api_key", "secret") == "password"
    assert editor.field_kind("units", "metric") == "select"
    assert editor.field_kind("language", "fr") == "select"
    assert editor.field_kind("layout.weather_mode", "after_character") == "select"
    assert editor.field_kind("weather_background_alpha", 1.0) == "slider"
    assert editor.field_kind("weather_background_alpha", 200) == "number"
    assert editor.field_kind("ambient_min_day_brightness", 0.22) == "slider"
    assert editor.field_kind("layout.character_center_x_pct", 0.28) == "slider"
    assert editor.field_kind("background_color", [255, 255, 255]) == "color"
    assert editor.field_kind("accessories_column.plate_color", [220, 224, 230, 230]) == "json"
    assert editor.field_kind("character_colorkey", None) == "json"
    assert editor.field_kind("character_colorkey", [0, 0, 0]) == "json"
    assert editor.field_kind("transit.bus_stops", {"56220": "Snowdon"}) == "json"
    assert editor.field_kind("transit.metro_directions", {"Snowdon": "Snowdon"}) == "json"
    assert editor.field_kind("fullscreen", True) == "bool"
    assert editor.field_kind("city", "Montreal,CA") == "text"
    assert editor.field_kind("layout", {"weather_mode": "after_character"}) == "section"


def test_validation_errors_do_not_change_other_keys():
    original = {"city": "Montreal,CA", "refresh_minutes": 5, "character_colorkey": None}
    built, errors = editor.build_config(
        original,
        {
            "city": "Québec,CA",
            "refresh_minutes": "3.5",
            "character_colorkey": "{",
        },
    )
    assert any(item.startswith("refresh_minutes") for item in errors)
    assert any("JSON invalide" in item for item in errors)
    assert built["city"] == "Québec,CA"
    assert built["refresh_minutes"] == 5
    assert built["character_colorkey"] is None


def test_slider_rejects_values_outside_unit_interval():
    built, errors = editor.build_config(
        {"weather_background_alpha": 1.0},
        {"weather_background_alpha": "1.4"},
    )
    assert errors == ["weather_background_alpha : valeur entre 0 et 1 attendue."]
    assert built["weather_background_alpha"] == 1.0


def test_select_rejects_unknown_choice():
    built, errors = editor.build_config({"units": "metric"}, {"units": "kelvin"})
    assert errors == ["units : choix invalide."]
    assert built["units"] == "metric"


def test_missing_field_is_an_error():
    _built, errors = editor.build_config({"city": "Montreal,CA"}, {})
    assert errors == ["city : champ manquant."]


def test_checkbox_last_value_wins():
    action, fields = editor.parse_form(
        b"v:fullscreen=false&v:fullscreen=true&action=restart"
    )
    assert action == "restart"
    assert fields["fullscreen"] == "true"


def test_blank_secret_keeps_stored_value():
    original = {"api_key": "secret", "city": "Montreal,CA"}
    built, errors = editor.build_config(
        original, {"api_key": "", "city": "Québec,CA"}
    )
    assert errors == []
    assert built == {"api_key": "secret", "city": "Québec,CA"}


def test_typed_secret_replaces_stored_value():
    built, errors = editor.build_config(
        {"api_key": "secret"}, {"api_key": "nouveau"}
    )
    assert errors == []
    assert built["api_key"] == "nouveau"


def test_form_controls_for_example():
    config = json.loads(EXAMPLE.read_text(encoding="utf-8"))
    page = editor.render_page(config)
    assert '<input type="password" name="v:api_key" value=""' in page
    assert '<input type="password" name="v:transit.stm_api_key" value=""' in page
    assert "VOTRE_CLE_OPENWEATHERMAP_ICI" not in page
    assert "VOTRE_CLE_API_STM_ICI" not in page
    assert "Laisser vide pour conserver la clé actuelle." in page
    assert '<select name="v:units">' in page
    assert '<select name="v:language">' in page
    assert '<option value="fr" selected>fr</option>' in page
    assert '<option value="en">en</option>' in page or '<option value="en" selected>en</option>' in page
    assert '<select name="v:layout.weather_mode">' in page
    assert '<option value="after_character" selected>after_character</option>' in page
    assert 'name="v:weather_background_alpha"' in page
    assert 'type="range"' in page
    assert 'name="v:layout.character_center_x_pct"' in page
    assert '<input type="color" name="v:background_color" value="#ffffff">' in page
    assert '<input type="color" name="v:ambient_night_bg" value="#0a0c14">' in page
    assert '<input type="text" name="v:transit.metro_route_id"' in page
    assert 'name="v:character_colorkey"' in page
    assert 'name="v:transit.bus_stops"' in page
    assert 'name="v:accessories_column.plate_color"' in page
    assert "<legend>layout</legend>" in page
    assert "<legend>transit</legend>" in page
    assert "<legend>accessories_column</legend>" in page
    assert page.index("<legend>layout</legend>") < page.index('name="v:background_color"')
    assert page.index('name="v:background_color"') < page.index("<legend>transit</legend>")
    assert ">Enregistrer</button>" in page
    assert ">Redémarrer</button>" in page


def test_save_writes_backup_then_replaces(tmp_path, monkeypatch):
    config_path = tmp_path / "config.json"
    backup_path = tmp_path / "config.json.bak"
    config_path.write_text('{"city": "A"}\n', encoding="utf-8")
    monkeypatch.setattr(editor, "CONFIG_PATH", config_path)
    monkeypatch.setattr(editor, "BACKUP_PATH", backup_path)
    editor.save_config({"city": "B"})
    assert backup_path.read_text(encoding="utf-8") == '{"city": "A"}\n'
    assert json.loads(config_path.read_text(encoding="utf-8")) == {"city": "B"}
    assert not list(tmp_path.glob(".config.json.*.tmp"))


@pytest.fixture
def editor_server(tmp_path, monkeypatch):
    config_path = tmp_path / "config.json"
    backup_path = tmp_path / "config.json.bak"
    config_path.write_text(EXAMPLE.read_text(encoding="utf-8"), encoding="utf-8")
    monkeypatch.setattr(editor, "CONFIG_PATH", config_path)
    monkeypatch.setattr(editor, "BACKUP_PATH", backup_path)
    httpd = HTTPServer(("127.0.0.1", 0), editor.Handler)
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    try:
        yield httpd, config_path, backup_path
    finally:
        httpd.shutdown()
        httpd.server_close()
        thread.join(timeout=2)


def _post(httpd, pairs):
    port = httpd.server_address[1]
    data = urlencode(pairs).encode("utf-8")
    request = Request(
        f"http://127.0.0.1:{port}/",
        data=data,
        method="POST",
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    with urlopen(request) as response:
        return response.status, response.read().decode("utf-8")


def test_http_invalid_json_does_not_write(editor_server):
    httpd, config_path, backup_path = editor_server
    original = config_path.read_bytes()
    config = json.loads(original.decode("utf-8"))
    pairs = _walk_fields(config, bool_pair=True)
    pairs = [
        ("v:transit.bus_stops", "{") if key == "v:transit.bus_stops" else (key, value)
        for key, value in pairs
    ]
    pairs.append(("action", "save"))
    status, body = _post(httpd, pairs)
    assert status == 200
    assert "JSON invalide" in body
    assert config_path.read_bytes() == original
    assert not backup_path.exists()


def test_http_save_updates_city_and_keeps_backup(editor_server):
    httpd, config_path, backup_path = editor_server
    original = config_path.read_text(encoding="utf-8")
    config = json.loads(original)
    pairs = [
        (key, "Québec,CA") if key == "v:city" else (key, value)
        for key, value in _walk_fields(config, bool_pair=True)
    ]
    pairs.append(("action", "save"))
    status, body = _post(httpd, pairs)
    assert status == 200
    assert "Enregistré" in body
    assert "config.json.bak" in body
    saved = json.loads(config_path.read_text(encoding="utf-8"))
    assert saved["city"] == "Québec,CA"
    saved["city"] = config["city"]
    assert saved == config
    assert backup_path.read_text(encoding="utf-8") == original


def test_http_empty_save_does_not_overwrite(editor_server):
    httpd, config_path, backup_path = editor_server
    original = config_path.read_bytes()
    status, body = _post(httpd, [("action", "save")])
    assert status == 200
    assert "champ manquant" in body
    assert config_path.read_bytes() == original
    assert not backup_path.exists()


def test_http_restart_failure_keeps_file_and_unsaved_edit(editor_server, monkeypatch):
    httpd, config_path, backup_path = editor_server
    original = config_path.read_bytes()
    calls = []

    def fake_run(args, **kwargs):
        calls.append(args)
        return editor.subprocess.CompletedProcess(
            args, 1, "", "sudo: a password is required\n"
        )

    monkeypatch.setattr(editor.subprocess, "run", fake_run)
    status, body = _post(
        httpd,
        [("v:city", "Québec,CA"), ("action", "restart")],
    )
    assert status == 200
    assert calls == [["sudo", "-n", "systemctl", "restart", "weatherdress"]]
    assert "mot de passe" in body
    assert "Québec,CA" in body
    assert config_path.read_bytes() == original
    assert not backup_path.exists()


def test_http_restart_success(editor_server, monkeypatch):
    httpd, _config_path, _backup_path = editor_server

    def fake_run(args, **kwargs):
        return editor.subprocess.CompletedProcess(args, 0, "", "")

    monkeypatch.setattr(editor.subprocess, "run", fake_run)
    status, body = _post(httpd, [("action", "restart")])
    assert status == 200
    assert "Service weatherdress redémarré." in body


def test_secrets_stay_out_of_the_page_after_a_typed_value():
    page = editor.render_page(
        {"api_key": "secret-value", "transit": {"stm_api_key": "stm-secret"}},
        fields={"api_key": "typed-secret", "transit.stm_api_key": "typed-stm"},
    )
    assert "secret-value" not in page
    assert "stm-secret" not in page
    assert "typed-secret" not in page
    assert "typed-stm" not in page


def test_lan_host_requires_password_file(tmp_path):
    missing = tmp_path / "editor_password"
    assert editor.require_editor_password("127.0.0.1", missing) is None
    try:
        editor.require_editor_password("0.0.0.0", missing)
    except ValueError as exc:
        assert "introuvable" in str(exc)
    else:
        raise AssertionError("fichier manquant accepté")
    missing.write_text("\n", encoding="utf-8")
    try:
        editor.require_editor_password("0.0.0.0", missing)
    except ValueError as exc:
        assert "vide" in str(exc)
    else:
        raise AssertionError("fichier vide accepté")
    missing.write_text("s3cret\n", encoding="utf-8")
    assert editor.require_editor_password("0.0.0.0", missing) == "s3cret"


def test_main_refuses_to_bind_lan_without_password(monkeypatch, capsys):
    def missing(host, path=None):
        raise ValueError("Mot de passe de l'éditeur introuvable : /tmp/editor_password")

    monkeypatch.setattr(editor, "require_editor_password", missing)
    assert editor.main(["--host", "0.0.0.0", "--port", "8765"]) == 1
    assert "introuvable" in capsys.readouterr().err


def test_main_localhost_skips_password(monkeypatch):
    seen = {}

    class Dummy:
        def serve_forever(self):
            raise KeyboardInterrupt

        def server_close(self):
            pass

    def fake_server(addr, handler):
        seen["addr"] = addr
        return Dummy()

    monkeypatch.setattr(editor, "require_editor_password", lambda host, path=None: None)
    monkeypatch.setattr(editor, "HTTPServer", fake_server)
    assert editor.main(["--host", "127.0.0.1", "--port", "8765"]) == 0
    assert seen["addr"] == ("127.0.0.1", 8765)
    assert editor.EDITOR_PASSWORD is None


def _basic(user, password):
    token = base64.b64encode(f"{user}:{password}".encode()).decode("ascii")
    return f"Basic {token}"


def test_http_basic_auth(tmp_path, monkeypatch):
    config_path = tmp_path / "config.json"
    config_path.write_text('{"api_key": "secret-value", "city": "Montreal,CA"}\n', encoding="utf-8")
    monkeypatch.setattr(editor, "CONFIG_PATH", config_path)
    monkeypatch.setattr(editor, "BACKUP_PATH", tmp_path / "config.json.bak")
    monkeypatch.setattr(editor, "EDITOR_PASSWORD", "s3cret")
    httpd = HTTPServer(("127.0.0.1", 0), editor.Handler)
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    port = httpd.server_address[1]
    url = f"http://127.0.0.1:{port}/"
    try:
        with pytest.raises(HTTPError) as missing:
            urlopen(url)
        assert missing.value.code == 401
        assert "Basic" in missing.value.headers.get("WWW-Authenticate", "")
        wrong = Request(url, headers={"Authorization": _basic("weather", "nope")})
        with pytest.raises(HTTPError) as rejected:
            urlopen(wrong)
        assert rejected.value.code == 401
        good = Request(url, headers={"Authorization": _basic("ignored", "s3cret")})
        with urlopen(good) as response:
            status = response.status
            body = response.read().decode("utf-8")
        assert status == 200
        assert "secret-value" not in body
        assert 'name="v:api_key" value=""' in body
    finally:
        httpd.shutdown()
        httpd.server_close()
        thread.join(timeout=2)


def test_http_blank_secret_is_kept(editor_server):
    httpd, config_path, backup_path = editor_server
    original = json.loads(config_path.read_text(encoding="utf-8"))
    pairs = []
    for key, value in _walk_fields(original, bool_pair=True):
        if key in ("v:api_key", "v:transit.stm_api_key"):
            pairs.append((key, ""))
        elif key == "v:city":
            pairs.append((key, "Québec,CA"))
        else:
            pairs.append((key, value))
    pairs.append(("action", "save"))
    status, _body = _post(httpd, pairs)
    assert status == 200
    saved = json.loads(config_path.read_text(encoding="utf-8"))
    assert saved["city"] == "Québec,CA"
    assert saved["api_key"] == original["api_key"]
    assert saved["transit"]["stm_api_key"] == original["transit"]["stm_api_key"]
    assert backup_path.is_file()


def test_unknown_path_is_404():
    httpd = HTTPServer(("127.0.0.1", 0), editor.Handler)
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    try:
        port = httpd.server_address[1]
        with pytest.raises(HTTPError) as caught:
            urlopen(f"http://127.0.0.1:{port}/ailleurs")
        assert caught.value.code == 404
    finally:
        httpd.shutdown()
        httpd.server_close()
        thread.join(timeout=2)

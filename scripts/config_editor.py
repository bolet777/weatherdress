#!/usr/bin/env python3
"""Éditeur de config.json.

Par défaut, écoute sur 127.0.0.1:8765 sans mot de passe.
Avec --host autre que 127.0.0.1, HTTP Basic est obligatoire.
Le mot de passe est lu dans ~/.config/weatherdress/editor_password.
Voir docs/config-editor.md.
"""

import argparse
import base64
import html
import json
import math
import os
import re
import secrets
import shutil
import subprocess
import sys
import tempfile
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from urllib.parse import parse_qs

ROOT = Path(__file__).resolve().parent.parent
CONFIG_PATH = ROOT / "config.json"
BACKUP_PATH = ROOT / "config.json.bak"
LOCALE_DIR = ROOT / "locale"
EDITOR_PASSWORD_PATH = Path.home() / ".config" / "weatherdress" / "editor_password"

HOST = "127.0.0.1"
PORT = 8765
# None : pas d'authentification (écoute limitée à 127.0.0.1).
EDITOR_PASSWORD = None
MAX_BODY = 1_048_576

RAW_JSON_PATHS = {
    "character_colorkey",
    "transit.bus_stops",
    "transit.metro_directions",
}
PASSWORD_PATHS = {"api_key", "transit.stm_api_key"}
SLIDER_EXACT = {"weather_background_alpha", "ambient_min_day_brightness"}
SELECT_PATHS = {"units", "language", "layout.weather_mode"}

PAGE_HEAD = """<!DOCTYPE html>
<html lang="fr">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>WeatherDress — configuration</title>
<style>
  body { font: 15px/1.45 system-ui, sans-serif; color: #222; max-width: 42rem; margin: 1.5rem auto; padding: 0 1rem 2.5rem; }
  h1 { font-size: 1.35rem; font-weight: 650; margin-bottom: 0.25rem; }
  .lead { margin-top: 0; color: #444; }
  fieldset { border: 1px solid #ccc; margin: 1rem 0; padding: 0.4rem 0.9rem 0.7rem; }
  legend { font-family: ui-monospace, SFMono-Regular, Menlo, monospace; padding: 0 0.25rem; }
  label { display: grid; grid-template-columns: 15rem 1fr; gap: 0.5rem 0.8rem; align-items: center; margin: 0.35rem 0; }
  label.json, label.secret { align-items: start; }
  label.json .key, label.secret .key { padding-top: 0.35rem; }
  .key { font-family: ui-monospace, SFMono-Regular, Menlo, monospace; font-size: 0.82rem; word-break: break-word; }
  .control input[type="text"], .control input[type="password"], .control input[type="number"], .control select, .control textarea {
    width: 100%; box-sizing: border-box; font: 0.9rem ui-monospace, SFMono-Regular, Menlo, monospace; padding: 0.28rem 0.4rem;
  }
  textarea { min-height: 5.5rem; }
  .slider { display: flex; align-items: center; gap: 0.6rem; }
  .slider input[type="range"] { flex: 1; }
  .slider output { font-family: ui-monospace, SFMono-Regular, Menlo, monospace; min-width: 3.2rem; }
  .hint { display: block; margin-top: 0.2rem; color: #555; font-size: 0.78rem; }
  .msg { padding: 0.65rem 0.8rem; margin: 0.8rem 0; white-space: pre-wrap; }
  .ok { background: #e5f2e4; }
  .err { background: #f8e4e0; }
  .actions { display: flex; gap: 0.6rem; margin-top: 1rem; }
  button { font: inherit; padding: 0.4rem 0.85rem; border: 1px solid #222; background: #222; color: #fff; cursor: pointer; }
  button.secondary { background: #fff; color: #222; }
  @media (max-width: 640px) { label { grid-template-columns: 1fr; } }
</style>
</head>
<body>
<h1>Configuration</h1>
<p class="lead">Fichier config.json. Les changements s’appliquent après le redémarrage du service.</p>
"""

PAGE_FOOT = """
<script>
document.querySelectorAll("input[type=range]").forEach(function (input) {
  var output = input.parentNode.querySelector("output");
  function sync() { output.textContent = input.value; }
  input.addEventListener("input", sync);
  sync();
});
</script>
</body>
</html>
"""


def load_config():
    path = CONFIG_PATH
    if not path.is_file():
        return None, (
            "config.json introuvable. Copier config.example.json vers config.json."
        )
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        return None, f"config.json n'est pas du JSON valide (ligne {exc.lineno})."
    except OSError as exc:
        return None, f"Lecture de config.json impossible : {exc}"
    if not isinstance(data, dict):
        return None, "config.json doit contenir un objet JSON."
    return data, None


def dump_config(data):
    return _dump(data, 0) + "\n"


def _dump(data, level):
    indent = "  " * level
    if isinstance(data, dict):
        if not data:
            return "{}"
        lines = []
        items = list(data.items())
        for index, (key, value) in enumerate(items):
            comma = "," if index < len(items) - 1 else ""
            rendered = _dump(value, level + 1)
            key_text = json.dumps(key, ensure_ascii=False)
            lines.append(f"{'  ' * (level + 1)}{key_text}: {rendered}{comma}")
        return "{\n" + "\n".join(lines) + "\n" + indent + "}"
    if isinstance(data, list):
        if all(_is_scalar(item) for item in data):
            return "[" + ", ".join(_scalar(item) for item in data) + "]"
        inner = []
        for index, item in enumerate(data):
            comma = "," if index < len(data) - 1 else ""
            inner.append(f"{'  ' * (level + 1)}{_dump(item, level + 1)}{comma}")
        return "[\n" + "\n".join(inner) + "\n" + indent + "]"
    return _scalar(data)


def _is_scalar(data):
    return data is None or type(data) in (bool, int, float, str)


def _scalar(data):
    return json.dumps(data, ensure_ascii=False)


def save_config(data):
    text = dump_config(data)
    json.loads(text)
    if CONFIG_PATH.is_file():
        shutil.copy2(CONFIG_PATH, BACKUP_PATH)
    tmp_path = None
    try:
        fd, tmp_name = tempfile.mkstemp(
            dir=CONFIG_PATH.parent, prefix=".config.json.", suffix=".tmp"
        )
        tmp_path = Path(tmp_name)
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as handle:
            handle.write(text)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(tmp_path, CONFIG_PATH)
    except Exception:
        if tmp_path is not None and tmp_path.exists():
            tmp_path.unlink()
        raise


def languages():
    if not LOCALE_DIR.is_dir():
        return []
    return sorted(path.stem for path in LOCALE_DIR.glob("*.json") if path.is_file())


def select_choices(path, current):
    if path == "units":
        choices = ["metric", "imperial"]
    elif path == "language":
        choices = languages()
    elif path == "layout.weather_mode":
        choices = ["after_character", "screen_right"]
    else:
        choices = []
    if isinstance(current, str) and current not in choices:
        choices.append(current)
    return choices


def _is_slider_path(path):
    if path in SLIDER_EXACT:
        return True
    name = path.rsplit(".", 1)[-1]
    return path.startswith("layout.") and name.endswith("_pct")


def _unit_interval(value):
    if type(value) not in (int, float):
        return False
    number = float(value)
    return math.isfinite(number) and 0.0 <= number <= 1.0


def _is_rgb(value):
    if not isinstance(value, list) or len(value) != 3:
        return False
    for channel in value:
        if type(channel) is not int or not 0 <= channel <= 255:
            return False
    return True


def field_kind(path, value):
    """Contrôle du formulaire. Les chemins bruts passent avant les objets imbriqués."""
    if path in RAW_JSON_PATHS:
        return "json"
    if isinstance(value, dict):
        return "section"
    if path in PASSWORD_PATHS and isinstance(value, str):
        return "password"
    if path in SELECT_PATHS and isinstance(value, str):
        return "select"
    # Curseur seulement si la valeur tient déjà dans 0–1 (un alpha 0–255 reste un nombre).
    if _is_slider_path(path) and _unit_interval(value):
        return "slider"
    if type(value) is bool:
        return "bool"
    if type(value) in (int, float):
        return "number"
    if isinstance(value, str):
        return "text"
    if _is_rgb(value):
        return "color"
    return "json"


def format_value(kind, value):
    if kind == "bool":
        return "true" if value else "false"
    if kind == "number":
        if type(value) is int:
            return str(value)
        return json.dumps(value)
    if kind in ("text", "password", "select"):
        return value if isinstance(value, str) else ""
    if kind == "slider":
        return json.dumps(float(value))
    if kind == "color":
        return "#{:02x}{:02x}{:02x}".format(value[0], value[1], value[2])
    if kind == "json":
        return json.dumps(value, indent=2, ensure_ascii=False)
    return ""


def parse_field(kind, path, original, raw):
    if kind == "bool":
        if raw == "true":
            return True
        if raw == "false":
            return False
        raise ValueError("valeur booléenne attendue.")
    if kind == "number":
        return _parse_number(raw, original)
    if kind == "password":
        # Champ vide : la clé déjà enregistrée ne change pas.
        if raw == "":
            return original
        return raw
    if kind == "text":
        return raw
    if kind == "select":
        if raw not in select_choices(path, original):
            raise ValueError("choix invalide.")
        return raw
    if kind == "slider":
        number = _parse_finite(raw, "valeur entre 0 et 1 attendue.")
        if number < 0 or number > 1:
            raise ValueError("valeur entre 0 et 1 attendue.")
        return number
    if kind == "color":
        text = raw.strip()
        if not re.fullmatch(r"#[0-9a-fA-F]{6}", text):
            raise ValueError("couleur #rrggbb attendue.")
        return [int(text[1:3], 16), int(text[3:5], 16), int(text[5:7], 16)]
    if kind == "json":
        try:
            return json.loads(raw)
        except json.JSONDecodeError as exc:
            raise ValueError(
                f"JSON invalide ({exc.msg}, ligne {exc.lineno})."
            ) from exc
    raise ValueError("champ non reconnu.")


def _parse_finite(raw, message):
    try:
        number = float(str(raw).strip())
    except ValueError:
        raise ValueError(message) from None
    if not math.isfinite(number):
        raise ValueError(message)
    return number


def _parse_number(raw, original):
    if type(original) is int:
        number = _parse_finite(raw, "nombre entier attendu.")
        if not number.is_integer():
            raise ValueError("nombre entier attendu.")
        return int(number)
    return _parse_finite(raw, "nombre attendu.")


def build_config(original, fields):
    errors = []
    if not isinstance(original, dict):
        return original, ["config.json doit contenir un objet JSON."]
    built = _apply_dict(original, "", fields, errors)
    return built, errors


def _apply_dict(obj, prefix, fields, errors):
    built = {}
    for key, value in obj.items():
        path = f"{prefix}.{key}" if prefix else key
        built[key] = _apply_value(path, value, fields, errors)
    return built


def _apply_value(path, value, fields, errors):
    kind = field_kind(path, value)
    if kind == "section":
        if not isinstance(value, dict):
            errors.append(f"{path} : objet JSON attendu.")
            return value
        return _apply_dict(value, path, fields, errors)
    if path not in fields:
        errors.append(f"{path} : champ manquant.")
        return value
    try:
        return parse_field(kind, path, value, fields[path])
    except ValueError as exc:
        errors.append(f"{path} : {exc}")
        return value


def parse_form(body):
    parsed = parse_qs(body.decode("utf-8"), keep_blank_values=True)
    action_values = parsed.get("action") or ["save"]
    action = action_values[-1]
    fields = {}
    for key, values in parsed.items():
        if key.startswith("v:"):
            fields[key[2:]] = values[-1]
    return action, fields


def esc(value):
    return html.escape(str(value), quote=True)


def render_page(config, fields=None, notice=None, error=False, errors=None):
    parts = [PAGE_HEAD]
    if notice:
        kind = "err" if error else "ok"
        parts.append(f'<p class="msg {kind}">{esc(notice)}</p>')
    if errors:
        items = "".join(f"<li>{esc(item)}</li>" for item in errors)
        parts.append(f'<ul class="msg err">{items}</ul>')
    if isinstance(config, dict):
        parts.append(
            '<form method="post" action="/" autocomplete="off" accept-charset="UTF-8">'
        )
        parts.append(_render_object(config, "", fields))
        parts.append(
            '<div class="actions">'
            '<button type="submit" name="action" value="save">Enregistrer</button>'
            '<button type="submit" name="action" value="restart" class="secondary">'
            "Redémarrer</button>"
            "</div></form>"
        )
    parts.append(PAGE_FOOT)
    return "".join(parts)


def _render_object(obj, prefix, fields):
    chunks = []
    for key, value in obj.items():
        path = f"{prefix}.{key}" if prefix else key
        kind = field_kind(path, value)
        if kind == "section":
            chunks.append(f"<fieldset><legend>{esc(key)}</legend>")
            chunks.append(_render_object(value, path, fields))
            chunks.append("</fieldset>")
        else:
            chunks.append(_render_field(path, key, kind, value, fields))
    return "".join(chunks)


def _submitted_text(path, kind, value, fields):
    if fields is not None and path in fields:
        return fields[path]
    return format_value(kind, value)


def _render_field(path, key, kind, value, fields):
    raw = _submitted_text(path, kind, value, fields)
    name = f'name="v:{esc(path)}"'
    if kind == "bool":
        checked = " checked" if raw == "true" else ""
        control = (
            f'<input type="hidden" {name} value="false">'
            f'<input type="checkbox" {name} value="true"{checked}>'
        )
    elif kind == "password":
        control = (
            f'<input type="password" {name} value="" autocomplete="new-password" spellcheck="false">'
            '<span class="hint">Laisser vide pour conserver la clé actuelle.</span>'
        )
    elif kind == "select":
        choices = select_choices(path, value)
        if raw not in choices:
            choices = list(choices) + [raw]
        options = []
        for choice in choices:
            selected = " selected" if choice == raw else ""
            options.append(
                f'<option value="{esc(choice)}"{selected}>{esc(choice)}</option>'
            )
        control = f"<select {name}>{''.join(options)}</select>"
    elif kind == "slider":
        control = (
            '<span class="slider">'
            f'<input type="range" {name} min="0" max="1" step="0.01" value="{esc(raw)}">'
            f"<output>{esc(raw)}</output>"
            "</span>"
        )
    elif kind == "color" and re.fullmatch(r"#[0-9a-fA-F]{6}", raw.strip()):
        control = f'<input type="color" {name} value="{esc(raw.strip())}">'
    elif kind == "json":
        rows = min(16, max(4, raw.count("\n") + 1))
        control = (
            f'<textarea {name} rows="{rows}" spellcheck="false">{esc(raw)}</textarea>'
            '<span class="hint">JSON</span>'
        )
    else:
        input_type = "text"
        step = ""
        if kind == "number":
            try:
                float(str(raw).strip())
            except ValueError:
                input_type = "text"
            else:
                input_type = "number"
                step = ' step="1"' if type(value) is int else ' step="any"'
        control = (
            f'<input type="{input_type}" {name} value="{esc(raw)}"{step} spellcheck="false">'
        )
    css = "json" if kind == "json" else "secret" if kind == "password" else "field"
    return (
        f'<label class="{css}">'
        f'<span class="key">{esc(key)}</span>'
        f'<span class="control">{control}</span>'
        "</label>"
    )


def parse_args(argv):
    parser = argparse.ArgumentParser(description="Éditeur de config.json.")
    parser.add_argument(
        "--host",
        default=HOST,
        help="Adresse d'écoute (défaut : 127.0.0.1). Toute autre valeur exige un mot de passe.",
    )
    parser.add_argument("--port", type=int, default=PORT, help="Port (défaut : 8765).")
    return parser.parse_args(argv)


def require_editor_password(host, path=None):
    """Mot de passe HTTP Basic, ou None si l'écoute reste sur 127.0.0.1."""
    if host == "127.0.0.1":
        return None
    path = EDITOR_PASSWORD_PATH if path is None else path
    if not path.is_file():
        raise ValueError(
            f"Mot de passe de l'éditeur introuvable : {path}\n"
            "Créer le fichier (une ligne) avant d'écouter sur le réseau :\n"
            "  mkdir -p ~/.config/weatherdress\n"
            "  printf '%s\\n' 'votre-mot-de-passe' > ~/.config/weatherdress/editor_password\n"
            "  chmod 600 ~/.config/weatherdress/editor_password"
        )
    password = path.read_text(encoding="utf-8").strip()
    if not password:
        raise ValueError(f"Le fichier de mot de passe est vide : {path}")
    return password


def basic_password(header):
    if not header:
        return None
    scheme, _, token = header.partition(" ")
    if scheme.lower() != "basic" or not token.strip():
        return None
    try:
        decoded = base64.b64decode(token.strip(), validate=True).decode("utf-8")
    except (ValueError, UnicodeDecodeError):
        return None
    _user, separator, password = decoded.partition(":")
    if not separator:
        return None
    return password


def basic_auth_ok(header, expected):
    given = basic_password(header)
    if given is None:
        return False
    return secrets.compare_digest(given, expected)


def restart_service():
    command = ["sudo", "-n", "systemctl", "restart", "weatherdress"]
    try:
        completed = subprocess.run(
            command,
            capture_output=True,
            text=True,
            timeout=30,
        )
    except subprocess.TimeoutExpired:
        return False, "Délai dépassé pendant le redémarrage du service."
    except OSError as exc:
        return False, f"Redémarrage impossible : {exc}"
    if completed.returncode == 0:
        return True, "Service weatherdress redémarré."
    detail = (completed.stderr or completed.stdout or "").strip()
    if not detail:
        detail = f"Échec du redémarrage (code {completed.returncode})."
    lowered = detail.lower()
    if (
        "password is required" in lowered
        or "a terminal is required" in lowered
        or "no tty" in lowered
    ):
        detail += (
            "\nsudo demande un mot de passe. Ajouter la règle sudoers "
            "décrite dans docs/config-editor.md, ou lancer dans le SSH : "
            "sudo systemctl restart weatherdress"
        )
    return False, detail


class Handler(BaseHTTPRequestHandler):
    def _unauthorized(self):
        if not EDITOR_PASSWORD:
            return False
        if basic_auth_ok(self.headers.get("Authorization"), EDITOR_PASSWORD):
            return False
        message = "Authentification requise.\n".encode("utf-8")
        self.send_response(401)
        self.send_header(
            "WWW-Authenticate", 'Basic realm="WeatherDress", charset="UTF-8"'
        )
        self.send_header("Content-Type", "text/plain; charset=utf-8")
        self.send_header("Content-Length", str(len(message)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(message)
        return True

    def do_GET(self):
        if self._unauthorized():
            return
        path = self.path.split("?", 1)[0]
        if path == "/favicon.ico":
            self.send_response(204)
            self.end_headers()
            return
        if path != "/":
            self.send_html(404, render_page(None, notice="Page introuvable.", error=True))
            return
        config, load_error = load_config()
        if load_error:
            self.send_html(200, render_page(None, notice=load_error, error=True))
            return
        self.send_html(200, render_page(config))

    def do_POST(self):
        if self._unauthorized():
            return
        path = self.path.split("?", 1)[0]
        if path != "/":
            self.send_html(404, render_page(None, notice="Page introuvable.", error=True))
            return
        body = self._read_body()
        if body is None:
            return
        try:
            action, fields = parse_form(body)
        except UnicodeDecodeError:
            self.send_html(
                400, render_page(None, notice="Encodage de la requête illisible.", error=True)
            )
            return
        if action == "restart":
            ok, message = restart_service()
            config, load_error = load_config()
            self.send_html(
                200,
                render_page(
                    config,
                    fields=fields,
                    notice=load_error or message,
                    error=(not ok) or bool(load_error),
                ),
            )
            return
        if action != "save":
            config, load_error = load_config()
            self.send_html(
                200,
                render_page(
                    config,
                    fields=fields,
                    notice=load_error or "Action inconnue.",
                    error=True,
                ),
            )
            return
        config, load_error = load_config()
        if load_error:
            self.send_html(200, render_page(None, notice=load_error, error=True))
            return
        built, errors = build_config(config, fields)
        if errors:
            self.send_html(200, render_page(config, fields=fields, errors=errors))
            return
        try:
            save_config(built)
        except (OSError, ValueError, TypeError) as exc:
            self.send_html(
                200,
                render_page(
                    config,
                    fields=fields,
                    errors=[f"Écriture impossible : {exc}"],
                ),
            )
            return
        saved, saved_error = load_config()
        self.send_html(
            200,
            render_page(
                saved if saved_error is None else config,
                notice=(
                    saved_error
                    or "Enregistré. Copie précédente : config.json.bak. "
                    "Redémarrer le service pour appliquer."
                ),
                error=bool(saved_error),
            ),
        )

    def _read_body(self):
        try:
            length = int(self.headers.get("Content-Length", ""))
        except ValueError:
            self.send_html(400, render_page(None, notice="Requête invalide.", error=True))
            return None
        if length < 0 or length > MAX_BODY:
            self.send_html(
                400, render_page(None, notice="Requête trop volumineuse.", error=True)
            )
            return None
        return self.rfile.read(length)

    def send_html(self, status, body):
        data = body.encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(data)


def main(argv=None):
    global EDITOR_PASSWORD, HOST, PORT
    args = parse_args(sys.argv[1:] if argv is None else argv)
    if not 1 <= args.port <= 65535:
        print("Port invalide.", file=sys.stderr)
        return 1
    try:
        password = require_editor_password(args.host)
    except ValueError as exc:
        print(exc, file=sys.stderr)
        return 1
    except OSError as exc:
        print(f"Lecture du mot de passe impossible : {exc}", file=sys.stderr)
        return 1
    HOST = args.host
    PORT = args.port
    EDITOR_PASSWORD = password
    try:
        server = HTTPServer((HOST, PORT), Handler)
    except OSError as exc:
        print(f"Impossible d'écouter sur {HOST}:{PORT} : {exc}", file=sys.stderr)
        return 1
    print(f"Éditeur : http://{HOST}:{PORT}", flush=True)
    if password:
        print("Mot de passe requis (HTTP Basic).", flush=True)
    else:
        print("Écoute locale, sans mot de passe.", flush=True)
    print("Arrêt : Ctrl+C", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print()
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    sys.exit(main())

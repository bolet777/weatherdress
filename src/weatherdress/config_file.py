"""config.default.json, puis surcharges de config.json.

Les objets imbriqués sont fusionnés clé par clé. Les dictionnaires de
données (arrêts de bus, directions de métro) sont remplacés en entier.
"""

import copy
import json
import os
import shutil
import sys
import tempfile
from pathlib import Path

from .paths import CONFIG_PATH, REPO_ROOT

DEFAULT_CONFIG_PATH = REPO_ROOT / "config.default.json"
BACKUP_PATH = REPO_ROOT / "config.json.bak"

# Dictionnaires de données : la surcharge remplace l'objet, sans fusion.
REPLACE_PATHS = frozenset({
    "transit.bus_stops",
    "transit.metro_directions",
})

_OMIT = object()


def merge_config(base, override, path=""):
    """Recopie base et applique override. Les dict imbriqués sont fusionnés."""
    if not isinstance(base, dict) or not isinstance(override, dict):
        return copy.deepcopy(override)
    merged = copy.deepcopy(base)
    for key, value in override.items():
        child = f"{path}.{key}" if path else key
        current = merged.get(key)
        if (
            child in REPLACE_PATHS
            or not isinstance(current, dict)
            or not isinstance(value, dict)
        ):
            merged[key] = copy.deepcopy(value)
        else:
            merged[key] = merge_config(current, value, child)
    return merged


def overrides_only(default, current):
    """Partie de current différente de default. {} si rien ne change."""
    diffed = _diff(default, current, "")
    if diffed is _OMIT:
        return {}
    return diffed


def _diff(default, current, path):
    if path in REPLACE_PATHS:
        if current != default:
            return copy.deepcopy(current)
        return _OMIT
    if isinstance(default, dict) and isinstance(current, dict):
        out = {}
        for key, value in current.items():
            child = f"{path}.{key}" if path else key
            if key not in default:
                out[key] = copy.deepcopy(value)
                continue
            diffed = _diff(default[key], value, child)
            if diffed is not _OMIT:
                out[key] = diffed
        if not out:
            return _OMIT
        return out
    if current != default:
        return copy.deepcopy(current)
    return _OMIT


def value_at(config, path):
    """Valeur au chemin pointé (layout.weather_mode). Lève KeyError si absent."""
    current = config
    for part in path.split("."):
        if not isinstance(current, dict) or part not in current:
            raise KeyError(path)
        current = current[part]
    return current


def unknown_key_paths(defaults, user):
    """Chemins de user absents de defaults.

    Un objet inconnu est listé une fois, pas ses enfants. Les entrées des
    dictionnaires de données (REPLACE_PATHS) ne sont pas des clés obsolètes.
    """
    found = []
    _collect_unknown(defaults, user, "", found)
    return found


def _collect_unknown(defaults, user, path, found):
    if path in REPLACE_PATHS or not isinstance(user, dict) or not isinstance(defaults, dict):
        return
    for key, value in user.items():
        child = f"{path}.{key}" if path else key
        if key not in defaults:
            found.append(child)
            continue
        _collect_unknown(defaults[key], value, child, found)


def without_unknown_keys(defaults, user):
    """Copie de user sans les clés absentes de defaults."""
    if not isinstance(user, dict):
        return copy.deepcopy(user)
    return _drop_unknown(defaults, user, "")


def _drop_unknown(defaults, user, path):
    if path in REPLACE_PATHS or not isinstance(user, dict) or not isinstance(defaults, dict):
        return copy.deepcopy(user)
    out = {}
    for key, value in user.items():
        if key not in defaults:
            continue
        child = f"{path}.{key}" if path else key
        if (
            isinstance(value, dict)
            and isinstance(defaults[key], dict)
            and child not in REPLACE_PATHS
        ):
            stripped = _drop_unknown(defaults[key], value, child)
            if stripped:
                out[key] = stripped
        else:
            out[key] = copy.deepcopy(value)
    return out


def delete_key_path(config, path):
    """Retire path. Les dictionnaires parents devenus vides sont retirés aussi."""
    if not isinstance(config, dict) or not path:
        return False
    parts = path.split(".")
    parents = []
    node = config
    for part in parts[:-1]:
        child = node.get(part) if isinstance(node, dict) else None
        if not isinstance(child, dict):
            return False
        parents.append((node, part))
        node = child
    leaf = parts[-1]
    if not isinstance(node, dict) or leaf not in node:
        return False
    del node[leaf]
    for parent, key in reversed(parents):
        child = parent.get(key)
        if isinstance(child, dict) and not child:
            del parent[key]
        else:
            break
    return True


def read_json_object(path: Path):
    """(objet, None) ou (None, message). Le fichier absent est une erreur."""
    if not path.is_file():
        return None, f"{path.name} introuvable."
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        return None, f"{path.name} n'est pas du JSON valide (ligne {exc.lineno})."
    except OSError as exc:
        return None, f"Lecture de {path.name} impossible : {exc}"
    if not isinstance(data, dict):
        return None, f"{path.name} doit contenir un objet JSON."
    return data, None


def load_config():
    """Défauts de config.default.json, puis config.json fusionné par-dessus.

    Si config.json n'existe pas, retourne les défauts. Les objets imbriqués
    (layout, accessories_column, transit) sont fusionnés clé par clé.
    transit.bus_stops et transit.metro_directions sont remplacés en entier.
    """
    defaults, error = read_json_object(DEFAULT_CONFIG_PATH)
    if error:
        print(f"Erreur : {error}")
        sys.exit(1)
    if not CONFIG_PATH.is_file():
        return defaults
    user, error = read_json_object(CONFIG_PATH)
    if error:
        print(f"Erreur : {error}")
        sys.exit(1)
    return merge_config(defaults, user)


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


def save_json_file(path: Path, data, backup_path: Path):
    """Écrit data en JSON (fichier temporaire, puis remplacement). Copie .bak si le fichier existe."""
    text = dump_config(data)
    json.loads(text)
    if path.is_file():
        shutil.copy2(path, backup_path)
    tmp_path = None
    try:
        fd, tmp_name = tempfile.mkstemp(
            dir=path.parent, prefix=".config.json.", suffix=".tmp"
        )
        tmp_path = Path(tmp_name)
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as handle:
            handle.write(text)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(tmp_path, path)
    except Exception:
        if tmp_path is not None and tmp_path.exists():
            tmp_path.unlink()
        raise

#!/usr/bin/env python3
"""Retire de config.json les valeurs identiques à config.default.json.

À lancer une fois sur le Pi si config.json est encore une copie complète.
Copie l'ancien fichier vers config.json.bak avant de réécrire.
"""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from weatherdress import config_file


def main():
    defaults, error = config_file.read_json_object(config_file.DEFAULT_CONFIG_PATH)
    if error:
        print(f"Erreur : {error}", file=sys.stderr)
        return 1
    path = config_file.CONFIG_PATH
    if not path.is_file():
        print("config.json absent, rien à nettoyer.")
        return 0
    user, error = config_file.read_json_object(path)
    if error:
        print(f"Erreur : {error}", file=sys.stderr)
        return 1
    cleaned = config_file.overrides_only(
        defaults, config_file.merge_config(defaults, user)
    )
    if cleaned == user:
        print("config.json ne contient déjà que les surcharges.")
        return 0
    config_file.save_json_file(path, cleaned, config_file.BACKUP_PATH)
    print("config.json nettoyé. Copie précédente : config.json.bak.")
    return 0


if __name__ == "__main__":
    sys.exit(main())

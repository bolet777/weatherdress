"""Racine du dépôt : config.json, images/, locale/ au niveau du clone."""

from pathlib import Path

_PKG_DIR = Path(__file__).resolve().parent
REPO_ROOT = _PKG_DIR.parents[1]
CONFIG_PATH = REPO_ROOT / "config.json"
IMAGES_DIR = str(REPO_ROOT / "images")
LOCALES_DIR = REPO_ROOT / "locale"

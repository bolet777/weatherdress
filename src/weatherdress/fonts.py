"""Inter embarqué, une graisse par rôle.

``pygame.font.SysFont("sans-serif")`` suit la police de la machine.
``pygame.font.Font`` charge le fichier embarqué, donc le rendu reste le même.

Au même corps, l'interligne d'Inter est plus haut que celui de la FreeSans
fournie par ``SysFont`` (environ 88 px contre 49 px à un corps de 72).
Les tailles configurées ne sont pas compensées ici.

Graisses :
- light : grande température
- regular : descriptions et textes secondaires
- medium : petits textes lus de loin
- semibold : titres et bandeau
- semibold-tabular : heure et horaires (chiffres de largeur fixe)
"""

from pathlib import Path

import pygame

_DIR = Path(__file__).resolve().parents[2] / "fonts" / "inter"

ROLES = ("light", "regular", "medium", "semibold", "semibold-tabular")

_FILES = {
    "light": "Inter-Light.ttf",
    "regular": "Inter-Regular.ttf",
    "medium": "Inter-Medium.ttf",
    "semibold": "Inter-SemiBold.ttf",
    "semibold-tabular": "Inter-SemiBold-Tabular.ttf",
}

_cache = {}
_roles = {}


def load(px, role):
    """Police Inter à ``px``. Le même objet est réutilisé pour ce rôle et cette taille."""
    px = max(1, int(px))
    key = (role, px)
    cached = _cache.get(key)
    if cached is not None:
        return cached
    filename = _FILES.get(role)
    if filename is None:
        raise ValueError(f"rôle de police inconnu : {role}")
    path = _DIR / filename
    if not path.is_file():
        raise FileNotFoundError(f"police introuvable : {path}")
    font = pygame.font.Font(str(path), px)
    _roles[id(font)] = role
    _cache[key] = font
    return font


def role_of(font):
    """Rôle passé à ``load``, ou None si la police ne vient pas d'ici."""
    return _roles.get(id(font))

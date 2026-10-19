#!/usr/bin/env python3
"""Éditeur de config.json.

Affiche config.default.json fusionné avec config.json.
L'enregistrement n'écrit que les valeurs différentes du défaut.
Par défaut, écoute sur 127.0.0.1:8765 sans mot de passe.
Avec --host autre que 127.0.0.1, HTTP Basic est obligatoire.
Le mot de passe est lu dans ~/.config/weatherdress/editor_password.
Voir docs/config-editor.md.
"""

import argparse
import base64
import copy
import html
import json
import math
import re
import secrets
import subprocess
import sys
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from urllib.parse import parse_qs

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from weatherdress import config_file

CONFIG_PATH = ROOT / "config.json"
BACKUP_PATH = ROOT / "config.json.bak"
DEFAULT_CONFIG_PATH = config_file.DEFAULT_CONFIG_PATH
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

HELP = {
    "api_key": (
        "Clé OpenWeatherMap. Une clé refusée remplace l’écran par un message d’erreur."
    ),
    "city": (
        "Ville demandée à OpenWeatherMap, format Ville,PAYS (ex. Montreal,CA). "
        "Elle choisit la météo affichée, donc le fond, la tenue et le texte."
    ),
    "language": (
        "Langue des textes de l’interface et des descriptions météo. "
        "fr ou en, selon les fichiers de locale/."
    ),
    "units": (
        "Unité de la température affichée. metric = °C, imperial = °F. "
        "Les seuils de tenue sont en Celsius."
    ),
    "use_weather_background": (
        "Photo de fond selon la météo, recadrée plein écran. "
        "Désactivé : couleur unie et médaillon circulaire derrière le personnage."
    ),
    "weather_background_alpha": (
        "Opacité de l’image de fond météo, de 0 à 1. "
        "1 = photo opaque, plus bas = la couleur derrière transparaît "
        "(couleur d’ambiance si elle est activée, sinon background_color)."
    ),
    "refresh_minutes": (
        "Minutes entre deux lectures de la météo. "
        "Plus bas = température, tenue et accessoires futurs revus plus souvent."
    ),
    "forecast_hours": (
        "Horizon des accessoires futurs, en heures. "
        "Plus grand = pastilles plus lointaines, et l’anneau « bientôt » s’étale sur une plus longue fenêtre."
    ),
    "use_ambient_weather_background": (
        "Couleur sous la photo et opacité selon le lever, le coucher et les nuages. "
        "Désactivé : fond fixe (background_color) et opacité fixe."
    ),
    "ambient_twilight_minutes": (
        "Minutes de fondu de chaque côté du lever et du coucher. "
        "Plus grand = aube et crépuscule plus longs."
    ),
    "ambient_min_day_brightness": (
        "Luminosité minimale en plein jour par ciel couvert, de 0 à 1. "
        "Plus haut = le midi nuageux reste plus clair."
    ),
    "ambient_night_bg": (
        "Couleur sous la photo la nuit, [R, G, B] de 0 à 255. "
        "Visible quand l’ambiance est activée."
    ),
    "ambient_day_clear_bg": (
        "Couleur sous la photo en journée par ciel dégagé, [R, G, B]. "
        "Visible quand l’ambiance est activée."
    ),
    "ambient_day_overcast_bg": (
        "Couleur mélangée sous la photo quand il fait jour et nuageux, [R, G, B]. "
        "Visible quand l’ambiance est activée."
    ),
    "background_color": (
        "Couleur de fond [R, G, B] sans photo, et sous une photo translucide si l’ambiance est désactivée. "
        "Un fond sombre affiche en clair le texte des écrans d’attente."
    ),
    "circle_background_color": (
        "Couleur du médaillon circulaire derrière le personnage, [R, G, B]. "
        "Visible seulement sans photo de fond météo."
    ),
    "character_colorkey": (
        "null = désactivé. [R, G, B] rend cette couleur transparente sur le personnage et les accessoires. "
        "Utile pour un PNG sans canal alpha ; tout pixel de cette couleur disparaît."
    ),
    "fullscreen": (
        "true = plein écran à la résolution du moniteur, curseur masqué. "
        "false = fenêtre de screen_width × screen_height."
    ),
    "screen_width": "Largeur de la fenêtre en pixels. Ignorée en plein écran.",
    "screen_height": "Hauteur de la fenêtre en pixels. Ignorée en plein écran.",
    "debug_preview": (
        "true = météos fictives à la place de l’API, pour enchaîner tenues et fonds. "
        "false = météo réelle."
    ),
    "debug_preview_interval_seconds": (
        "Secondes entre deux météos fictives. Plus bas = défilement plus rapide "
        "(minimum effectif 0,5). Utilisé quand l’aperçu est activé."
    ),
    "identity_on_each_refresh": (
        "true = nouveau personnage à chaque lecture météo. "
        "false = personnage tiré une fois au démarrage et gardé."
    ),
    "character_variant_max": (
        "Numéro max des sprites tirés au sort (fichiers …1.png, …2.png, …). "
        "0 ou moins = toutes les variantes présentes sur le disque."
    ),
    "layout.character_center_x_pct": (
        "Position horizontale du centre du personnage, de 0 (bord gauche) à 1 (bord droit). "
        "Plus haut = plus à droite."
    ),
    "layout.character_center_y_offset_px": (
        "Décalage vertical du personnage par rapport au milieu de l’écran, en pixels. "
        "Négatif = plus haut, positif = plus bas."
    ),
    "layout.character_max_width_pct": (
        "Largeur max du personnage, en fraction de la largeur d’écran (0–1). "
        "Plus haut = sprite plus large, sans dépasser la taille du fichier."
    ),
    "layout.character_max_height_pct": (
        "Hauteur max du personnage, en fraction de la hauteur d’écran (0–1). "
        "Plus haut = sprite plus grand, sans dépasser la taille du fichier."
    ),
    "layout.weather_mode": (
        "after_character = texte météo à droite du personnage, centré verticalement sur lui. "
        "screen_right = texte aligné au bord droit, centré verticalement."
    ),
    "layout.weather_screen_right_margin_pct": (
        "Marge entre le texte météo et le bord droit, en fraction de la largeur (0–1, au moins 16 px). "
        "Plus haut = texte plus à gauche, moins de place pour la description."
    ),
    "layout.weather_gap_after_character_px": (
        "Espace en pixels entre le personnage et le texte météo, en mode after_character. "
        "Plus haut = texte plus éloigné du sprite."
    ),
    "layout.weather_transit_vertical_offset_px": (
        "Décalage vertical en pixels de la colonne météo et transport, après centrage sur le personnage. "
        "Négatif = remonte l’ensemble, positif = le descend."
    ),
    "layout.weather_temp_font_min": (
        "Taille minimale de la température, en pixels. "
        "La taille suit la hauteur d’écran et ne descend pas sous ce plancher."
    ),
    "layout.weather_temp_font_max": (
        "Taille maximale de la température, en pixels. "
        "Sur un grand écran, augmenter cette valeur agrandit le chiffre."
    ),
    "layout.weather_desc_font_min": (
        "Taille minimale de la description météo, en pixels. "
        "Plancher utilisé quand l’écran est petit."
    ),
    "layout.weather_desc_font_max": (
        "Taille maximale de la description météo, en pixels. "
        "Plafond utilisé quand l’écran est grand."
    ),
    "accessories_column.plate_color": (
        "Couleur du disque derrière chaque icône d’accessoire, [R, G, B] ou [R, G, B, A]. "
        "Le 4e nombre (0–255) est l’opacité ; sans lui, le disque est opaque."
    ),
    "accessories_column.track_color": (
        "Couleur de l’anneau de fond autour des accessoires, [R, G, B] ou [R, G, B, A]. "
        "L’arc d’urgence (vert bientôt, rouge plus tard) se dessine par-dessus."
    ),
    "transit.stm_api_key": (
        "Clé API STM pour les prochains bus. "
        "Vide ou placeholder : les cartes bus restent sans horaire. "
        "La variable STM_API_KEY, si elle est définie, est utilisée à la place."
    ),
    "transit.gtfs_url": (
        "Adresse du zip GTFS STM, source des horaires métro. "
        "Le panneau transport s’affiche quand cette adresse, la station et le numéro de ligne sont renseignés."
    ),
    "transit.bus_stops": (
        "Arrêts de bus suivis, objet JSON {identifiant STM: libellé}. "
        "Le libellé est le sous-titre de la carte ; l’identifiant sert à lire les passages."
    ),
    "transit.metro_station": (
        "Nom de station cherché dans le GTFS (extrait du nom, sans tenir compte de la casse). "
        "Affiché en titre de carte, précédé de « Station »."
    ),
    "transit.metro_route_id": (
        "Identifiant GTFS de la ligne de métro (ex. 5 pour la bleue). "
        "Seuls les passages de cette ligne sont affichés."
    ),
    "transit.metro_line_color": (
        "Couleur du bandeau gauche des cartes métro, [R, G, B]. "
        "Le bandeau bus reste bleu foncé."
    ),
    "transit.metro_directions": (
        "Libellés des directions, objet JSON {trip_headsign GTFS exact: texte court}. "
        "Le texte s’affiche sous la station, précédé de « Direction »."
    ),
    "transit.transit_refresh_seconds": (
        "Secondes entre deux lectures des horaires bus et métro. "
        "Plus bas = les minutes affichées se mettent à jour plus souvent."
    ),
    "transit.transit_alternate_seconds": (
        "Secondes avant de passer à l’arrêt de bus et à la direction métro suivants. "
        "0 = toutes les cartes en même temps. Plus haut = chaque carte reste plus longtemps."
    ),
    "transit.card_title_font_px": (
        "Taille du titre des cartes (bus ou station), en pixels, bornée de 10 à 48. "
        "Plus grand = titre plus gros et carte plus haute."
    ),
    "transit.card_subtitle_font_px": (
        "Taille du sous-titre (arrêt ou direction), en pixels, bornée de 8 à 40. "
        "Plus grand = carte plus haute."
    ),
    "transit.card_times_font_px": (
        "Taille des horaires (« 5min »), en pixels, bornée de 10 à 56. "
        "Plus grand = minutes plus lisibles et carte plus haute."
    ),
    "transit.strip_mode_letter_font_px": (
        "Taille de la lettre B ou M dans le bandeau, en pixels, bornée de 12 à 72. "
        "Elle s’affiche seulement si l’icône bus ou métro est absente."
    ),
    "transit.card_height_px": (
        "Hauteur forcée des cartes bus et métro, en pixels (48–200). "
        "null = hauteur calculée à partir des polices."
    ),
}

_GEAR = (
    '<svg viewBox="0 0 24 24" aria-hidden="true">'
    '<path fill="currentColor" d="M19.14 12.94a7.5 7.5 0 0 0 .06-.94 7.5 7.5 0 0 0-.06-.94l2.03-1.58a.5.5 0 0 0 .12-.64l-1.92-3.32a.5.5 0 0 0-.6-.22l-2.39.96a7.3 7.3 0 0 0-1.63-.94l-.36-2.54a.5.5 0 0 0-.5-.42h-3.84a.5.5 0 0 0-.5.42l-.36 2.54a7.3 7.3 0 0 0-1.63.94l-2.39-.96a.5.5 0 0 0-.6.22L2.71 8.84a.5.5 0 0 0 .12.64l2.03 1.58a7.5 7.5 0 0 0-.06.94c0 .32.02.63.06.94l-2.03 1.58a.5.5 0 0 0-.12.64l1.92 3.32a.5.5 0 0 0 .6.22l2.39-.96c.5.39 1.05.71 1.63.94l.36 2.54a.5.5 0 0 0 .5.42h3.84a.5.5 0 0 0 .5-.42l.36-2.54c.58-.23 1.13-.55 1.63-.94l2.39.96a.5.5 0 0 0 .6-.22l1.92-3.32a.5.5 0 0 0-.12-.64l-2.03-1.58zM12 15.5A3.5 3.5 0 1 1 12 8.5a3.5 3.5 0 0 1 0 7z"/>'
    "</svg>"
)
_EYE = (
    '<svg viewBox="0 0 24 24" aria-hidden="true">'
    '<path fill="none" stroke="currentColor" stroke-width="1.8" d="M2 12s3.6-7 10-7 10 7 10 7-3.6 7-10 7S2 12 2 12z"/>'
    '<circle cx="12" cy="12" r="2.6" fill="none" stroke="currentColor" stroke-width="1.8"/>'
    "</svg>"
)
_PIN = (
    '<svg viewBox="0 0 24 24" aria-hidden="true">'
    '<path fill="none" stroke="currentColor" stroke-width="1.8" d="M12 21s7-6.1 7-11a7 7 0 1 0-14 0c0 4.9 7 11 7 11z"/>'
    '<circle cx="12" cy="10" r="2.2" fill="currentColor"/>'
    "</svg>"
)

_SECTION_ORDER = (
    "Météo",
    "Ambiance",
    "Affichage",
    "Mise en page",
    "Accessoires",
    "Transport",
    "Autres",
)
_METEO_KEYS = {
    "api_key",
    "city",
    "language",
    "units",
    "use_weather_background",
    "weather_background_alpha",
    "refresh_minutes",
    "forecast_hours",
}
_AMBIANCE_KEYS = {
    "use_ambient_weather_background",
    "ambient_twilight_minutes",
    "ambient_min_day_brightness",
    "ambient_night_bg",
    "ambient_day_clear_bg",
    "ambient_day_overcast_bg",
    "background_color",
    "circle_background_color",
    "character_colorkey",
}
_AFFICHAGE_KEYS = {
    "fullscreen",
    "screen_width",
    "screen_height",
    "debug_preview",
    "debug_preview_interval_seconds",
    "identity_on_each_refresh",
    "character_variant_max",
}

PAGE_HEAD = """<!DOCTYPE html>
<html lang="fr">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>WeatherDress — configuration</title>
<style>
  * { box-sizing: border-box; }
  body {
    margin: 0; min-height: 100vh; background: #0f1623; color: #e6edf5;
    font: 15px/1.45 system-ui, sans-serif;
  }
  .card {
    width: min(900px, calc(100% - 2rem));
    margin: 1.25rem auto 2rem;
    background: #151d2b;
    border: 1px solid #253042;
    border-radius: 12px;
  }
  .head {
    display: flex; gap: 0.85rem; align-items: center;
    padding: 1.05rem 1.25rem 0.95rem;
    border-bottom: 1px solid #253042;
  }
  .badge {
    width: 42px; height: 42px; flex: none; border-radius: 10px;
    background: #1a3f73; color: #5aa2ff;
    display: grid; place-items: center;
  }
  .badge svg { width: 22px; height: 22px; }
  .head h1 { margin: 0; font-size: 1.35rem; font-weight: 700; letter-spacing: -0.02em; }
  .head p { margin: 0.12rem 0 0; color: #8b98ad; font-size: 0.92rem; }
  .settings { padding: 0.35rem 1.25rem 0.4rem; }
  .section {
    margin: 1.15rem 0 0.15rem; font-size: 0.72rem; font-weight: 700;
    letter-spacing: 0.07em; text-transform: uppercase; color: #8b98ad;
  }
  .section:first-child { margin-top: 0.7rem; }
  .row {
    display: grid; grid-template-columns: minmax(0, 2fr) minmax(0, 3fr);
    gap: 0.75rem 1.25rem; align-items: center;
    padding: 0.72rem 0; border-bottom: 1px solid #253042;
  }
  .row.json { align-items: start; }
  .row.json .name { padding-top: 0.45rem; }
  .name { display: flex; align-items: center; gap: 0.45rem; font-weight: 650; min-width: 0; }
  .name > span:first-child { overflow-wrap: anywhere; }
  .help { position: relative; display: inline-flex; flex: none; }
  .help-btn {
    width: 16px; height: 16px; border-radius: 50%; padding: 0;
    border: 1px solid #3d4f66; background: transparent; color: #8b98ad;
    font: 11px/14px system-ui, sans-serif; cursor: pointer;
  }
  .help-btn:hover, .help-btn:focus-visible { color: #e6edf5; border-color: #2f81f7; }
  .help-pop {
    display: none; position: absolute; z-index: 20; left: 0; top: calc(100% + 8px);
    width: max-content; max-width: 280px; padding: 0.45rem 0.6rem;
    background: #0f1623; color: #e6edf5; border: 1px solid #314158; border-radius: 8px;
    font-size: 0.78rem; font-weight: 450; line-height: 1.35;
    box-shadow: 0 10px 28px rgba(0, 0, 0, 0.35);
  }
  .help:hover .help-pop, .help:focus-within .help-pop, .help.open .help-pop { display: block; }
  .control input[type="text"], .control input[type="password"], .control input[type="number"], .control select, .control textarea {
    width: 100%; background: #0f1623; color: #e6edf5; border: 1px solid #314158;
    border-radius: 8px; padding: 0.48rem 0.7rem; font: inherit;
  }
  .control textarea {
    min-height: 5.6rem; resize: vertical;
    font-family: ui-monospace, SFMono-Regular, Menlo, monospace; font-size: 0.88rem;
  }
  .control input:focus, .control select:focus, .control textarea:focus {
    outline: none; border-color: #2f81f7; box-shadow: 0 0 0 3px rgba(47, 129, 247, 0.28);
  }
  .control select {
    appearance: none;
    background-image: url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='12' height='8' viewBox='0 0 12 8'%3E%3Cpath d='M1 1.2 L6 6.2 L11 1.2' fill='none' stroke='%238b98ad' stroke-width='1.6' stroke-linecap='round'/%3E%3C/svg%3E");
    background-repeat: no-repeat; background-position: right 0.75rem center; padding-right: 2rem;
  }
  .control input[type="number"]::-webkit-inner-spin-button,
  .control input[type="number"]::-webkit-outer-spin-button {
    opacity: 1; -webkit-appearance: inner-spin-button; filter: invert(0.85); height: 1.4rem;
  }
  .control .slider input.unit::-webkit-inner-spin-button,
  .control .slider input.unit::-webkit-outer-spin-button { display: none; }
  .secret-field, .text-field { position: relative; display: block; }
  .control .secret-field input, .control .text-field input { padding-right: 2.3rem; }
  .eye, .pin {
    position: absolute; right: 0.55rem; top: 50%; transform: translateY(-50%);
    color: #8b98ad; display: flex;
  }
  .eye { background: none; border: 0; padding: 0; cursor: pointer; }
  .eye:hover, .eye[aria-pressed="true"] { color: #e6edf5; }
  .pin { pointer-events: none; }
  .eye svg, .pin svg { width: 18px; height: 18px; }
  .switch { position: relative; display: inline-block; width: 44px; height: 26px; }
  .switch input[type="checkbox"] {
    position: absolute; inset: 0; margin: 0; opacity: 0; cursor: pointer; z-index: 1;
  }
  .switch .knob {
    position: absolute; inset: 0; border-radius: 999px; background: #2a3548; transition: background 0.15s;
  }
  .switch .knob:before {
    content: ""; position: absolute; width: 20px; height: 20px; left: 3px; top: 3px;
    border-radius: 50%; background: #fff; transition: transform 0.15s;
  }
  .switch input:checked + .knob { background: #2f81f7; }
  .switch input:checked + .knob:before { transform: translateX(18px); }
  .switch input:focus-visible + .knob { box-shadow: 0 0 0 3px rgba(47, 129, 247, 0.35); }
  .slider { display: flex; align-items: center; gap: 0.75rem; }
  .slider input[type="range"] {
    flex: 1; width: auto; height: 22px; margin: 0; background: transparent;
    -webkit-appearance: none; appearance: none;
  }
  .slider input[type="range"]:focus { outline: none; }
  .slider input[type="range"]::-webkit-slider-runnable-track {
    height: 6px; border-radius: 999px;
    background: linear-gradient(#2f81f7, #2f81f7) 0 / var(--pct, 0%) 100% no-repeat, #2c384c;
  }
  .slider input[type="range"]::-webkit-slider-thumb {
    -webkit-appearance: none; margin-top: -6px; width: 18px; height: 18px; border-radius: 50%;
    background: #fff; border: 3px solid #2f81f7;
  }
  .slider input[type="range"]::-moz-range-track { height: 6px; border-radius: 999px; background: #2c384c; border: 0; }
  .slider input[type="range"]::-moz-range-progress { height: 6px; border-radius: 999px; background: #2f81f7; }
  .slider input[type="range"]::-moz-range-thumb {
    width: 18px; height: 18px; border-radius: 50%; background: #fff; border: 3px solid #2f81f7;
  }
  .control .slider input.unit { width: 4.6rem; flex: none; text-align: center; font-variant-numeric: tabular-nums; }
  .color-field { display: flex; align-items: center; gap: 0.6rem; }
  .color-field input[type="color"] {
    width: 42px; height: 36px; padding: 3px; flex: none; border: 1px solid #314158;
    border-radius: 8px; background: #0f1623; cursor: pointer;
  }
  .color-field input[type="color"]::-webkit-color-swatch-wrapper { padding: 0; }
  .color-field input[type="color"]::-webkit-color-swatch { border: 0; border-radius: 4px; }
  .control .color-field input.hex {
    width: 7.2rem; flex: none; font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
    letter-spacing: 0.03em;
  }
  .json-tag { display: block; margin-top: 0.28rem; color: #8b98ad; font-size: 0.72rem; letter-spacing: 0.04em; }
  .bar {
    position: sticky; bottom: 0; z-index: 10;
    display: flex; align-items: center; justify-content: space-between; gap: 0.8rem;
    padding: 0.8rem 1.15rem; border-top: 1px solid #253042;
    background: #151d2b; border-radius: 0 0 12px 12px;
  }
  .messages { flex: 1; min-width: 0; }
  .msg { margin: 0; white-space: pre-wrap; font-size: 0.88rem; }
  .msg.ok { color: #3dd68c; }
  .msg.err { color: #ff7b72; }
  ul.msg { padding-left: 1.1rem; }
  .actions { display: flex; gap: 0.55rem; flex: none; }
  .actions button {
    font: inherit; border-radius: 8px; padding: 0.48rem 0.95rem; cursor: pointer;
  }
  .actions .primary { background: #2f81f7; color: #fff; border: 1px solid #2f81f7; font-weight: 650; }
  .actions .primary:hover { background: #4b94f8; }
  .actions .secondary { background: transparent; color: #e6edf5; border: 1px solid #314158; }
  .actions .secondary:hover { border-color: #8b98ad; }
  .mod-dot {
    width: 7px; height: 7px; border-radius: 50%; flex: none;
    background: transparent;
  }
  .row.modified .mod-dot { background: #2f81f7; }
  .reset {
    margin-left: auto; border: 0; background: transparent; color: #8b98ad;
    font: 16px/1 system-ui, sans-serif; cursor: pointer; padding: 0 0.1rem;
  }
  .reset:hover, .reset:focus-visible { color: #5aa2ff; }
  @media (max-width: 600px) {
    .row { grid-template-columns: 1fr; gap: 0.4rem; }
    .bar { flex-direction: column; align-items: stretch; }
    .actions { justify-content: flex-end; }
  }
</style>
</head>
<body>
<main class="card">
<header class="head">
  <span class="badge">""" + _GEAR + """</span>
  <div>
    <h1>Configuration</h1>
    <p>Défauts de config.default.json, surcharges de config.json. L’enregistrement n’écrit que les différences. Redémarrer le service pour appliquer.</p>
  </div>
</header>
"""

PAGE_FOOT = """
</main>
<script>
document.querySelectorAll(".slider").forEach(function (wrap) {
  var range = wrap.querySelector("input[type=range]");
  var num = wrap.querySelector("input.unit");
  function paint() {
    var n = Number(range.value);
    range.style.setProperty("--pct", (isFinite(n) ? n * 100 : 0) + "%");
  }
  function fromRange() { num.value = range.value; paint(); }
  function fromNum() {
    var n = parseFloat(num.value);
    if (!isFinite(n)) return;
    n = Math.max(0, Math.min(1, n));
    range.value = String(n);
    num.value = range.value;
    paint();
  }
  range.addEventListener("input", fromRange);
  num.addEventListener("input", fromNum);
  fromRange();
});
document.querySelectorAll(".color-field").forEach(function (wrap) {
  var picker = wrap.querySelector("input[type=color]");
  var hex = wrap.querySelector("input.hex");
  function toPicker() {
    if (/^#[0-9a-fA-F]{6}$/.test(hex.value)) picker.value = hex.value;
  }
  picker.addEventListener("input", function () { hex.value = picker.value.toUpperCase(); });
  hex.addEventListener("input", toPicker);
  hex.addEventListener("change", toPicker);
});
document.querySelectorAll(".eye").forEach(function (btn) {
  btn.addEventListener("click", function () {
    var input = btn.parentNode.querySelector("input");
    var show = input.type === "password";
    input.type = show ? "text" : "password";
    btn.setAttribute("aria-pressed", show ? "true" : "false");
    btn.setAttribute("aria-label", show ? "Masquer la clé" : "Afficher la clé");
  });
});
document.querySelectorAll(".help-btn").forEach(function (btn) {
  btn.addEventListener("click", function (event) {
    event.preventDefault();
    event.stopPropagation();
    var wrap = btn.parentNode;
    var open = wrap.classList.contains("open");
    document.querySelectorAll(".help.open").forEach(function (el) { el.classList.remove("open"); });
    if (!open) wrap.classList.add("open");
  });
});
document.addEventListener("click", function () {
  document.querySelectorAll(".help.open").forEach(function (el) { el.classList.remove("open"); });
});
function rowValue(row) {
  var kind = row.getAttribute("data-kind");
  if (kind === "bool") {
    var box = row.querySelector("input[type=checkbox]");
    return box && box.checked ? "true" : "false";
  }
  if (kind === "password") {
    var secret = row.querySelector(".secret-field input");
    return secret ? secret.value : "";
  }
  if (kind === "slider") return row.querySelector("input[type=range]").value;
  if (kind === "color") return row.querySelector("input[type=color]").value;
  if (kind === "json") return row.querySelector("textarea").value;
  var named = row.querySelector("[name^='v:']");
  return named ? named.value : "";
}
function setRowValue(row, value) {
  var kind = row.getAttribute("data-kind");
  if (kind === "bool") {
    row.querySelector("input[type=checkbox]").checked = value === "true";
    return;
  }
  if (kind === "slider") {
    var range = row.querySelector("input[type=range]");
    var num = row.querySelector("input.unit");
    range.value = value;
    if (num) num.value = value;
    range.dispatchEvent(new Event("input"));
    return;
  }
  if (kind === "color") {
    var picker = row.querySelector("input[type=color]");
    var hex = row.querySelector("input.hex");
    if (picker) picker.value = value;
    if (hex) hex.value = value.toUpperCase();
    return;
  }
  if (kind === "json") {
    row.querySelector("textarea").value = value;
    return;
  }
  var named = row.querySelector("input[name^='v:'], select[name^='v:'], textarea[name^='v:']");
  if (named) named.value = value;
}
function syncRow(row) {
  var flag = row.querySelector(".reset-flag");
  var kind = row.getAttribute("data-kind");
  if (kind === "password") {
    var typed = rowValue(row);
    if (typed) {
      if (flag) flag.value = "";
      row.classList.add("modified");
      return;
    }
    if (flag && flag.value === "1") {
      row.classList.remove("modified");
      return;
    }
    row.classList.toggle("modified", row.getAttribute("data-initial-modified") === "1");
    return;
  }
  var same = rowValue(row) === (row.getAttribute("data-default") || "");
  row.classList.toggle("modified", !same);
  if (flag) flag.value = same ? "1" : "";
}
document.querySelectorAll(".row").forEach(function (row) {
  row.addEventListener("input", function () { syncRow(row); });
  row.addEventListener("change", function () { syncRow(row); });
});
document.querySelectorAll(".reset").forEach(function (btn) {
  btn.addEventListener("click", function () {
    var row = btn.closest(".row");
    var flag = row.querySelector(".reset-flag");
    if (row.getAttribute("data-kind") === "password") {
      if (flag) flag.value = "1";
      var input = row.querySelector(".secret-field input");
      if (input) input.value = "";
      row.classList.remove("modified");
      return;
    }
    setRowValue(row, row.getAttribute("data-default") || "");
    syncRow(row);
  });
});
</script>
</body>
</html>
"""


def load_layers():
    """(défauts, fusion, None) ou (None, None, message).

    config.json absent : la fusion est une copie des défauts.
    """
    defaults, error = config_file.read_json_object(DEFAULT_CONFIG_PATH)
    if error:
        return None, None, error
    if not CONFIG_PATH.is_file():
        return defaults, config_file.merge_config(defaults, {}), None
    user, error = config_file.read_json_object(CONFIG_PATH)
    if error:
        return None, None, error
    return defaults, config_file.merge_config(defaults, user), None


def dump_config(data):
    return config_file.dump_config(data)


def save_config(data):
    config_file.save_json_file(CONFIG_PATH, data, BACKUP_PATH)


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


def build_config(original, fields, defaults=None, resets=None):
    errors = []
    if not isinstance(original, dict):
        return original, ["config.json doit contenir un objet JSON."]
    built = _apply_dict(original, "", fields, errors, defaults, resets or set())
    return built, errors


def _apply_dict(obj, prefix, fields, errors, defaults, resets):
    built = {}
    for key, value in obj.items():
        path = f"{prefix}.{key}" if prefix else key
        built[key] = _apply_value(path, value, fields, errors, defaults, resets)
    return built


def _apply_value(path, value, fields, errors, defaults, resets):
    kind = field_kind(path, value)
    if kind == "section":
        if not isinstance(value, dict):
            errors.append(f"{path} : objet JSON attendu.")
            return value
        return _apply_dict(value, path, fields, errors, defaults, resets)
    if path in resets:
        if defaults is None:
            errors.append(f"{path} : pas de valeur par défaut.")
            return value
        try:
            return copy.deepcopy(config_file.value_at(defaults, path))
        except KeyError:
            errors.append(f"{path} : pas de valeur par défaut.")
            return value
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
    resets = set()
    for key, values in parsed.items():
        if key.startswith("v:"):
            fields[key[2:]] = values[-1]
        elif key.startswith("reset:") and values[-1] == "1":
            resets.add(key[len("reset:"):])
    return action, fields, resets


def esc(value):
    return html.escape(str(value), quote=True)


def render_page(config, fields=None, notice=None, error=False, errors=None, defaults=None):
    parts = [PAGE_HEAD]
    messages = _render_messages(notice, error, errors)
    if isinstance(config, dict):
        parts.append(
            '<form method="post" action="/" autocomplete="off" accept-charset="UTF-8">'
        )
        parts.append('<div class="settings">')
        parts.append(_render_settings(config, fields, defaults))
        parts.append("</div>")
        parts.append('<div class="bar"><div class="messages">')
        parts.append(messages)
        parts.append("</div>")
        parts.append(
            '<div class="actions">'
            '<button type="submit" class="primary" name="action" value="save">Enregistrer</button>'
            '<button type="submit" class="secondary" name="action" value="restart">'
            "Redémarrer le service</button>"
            "</div></div></form>"
        )
    else:
        parts.append(f'<div class="bar"><div class="messages">{messages}</div></div>')
    parts.append(PAGE_FOOT)
    return "".join(parts)


def _render_messages(notice, error, errors):
    chunks = []
    if notice:
        kind = "err" if error else "ok"
        chunks.append(f'<p class="msg {kind}">{esc(notice)}</p>')
    if errors:
        items = "".join(f"<li>{esc(item)}</li>" for item in errors)
        chunks.append(f'<ul class="msg err">{items}</ul>')
    return "".join(chunks)


def _render_settings(config, fields, defaults):
    grouped = {name: [] for name in _SECTION_ORDER}
    for item in _collect_fields(config, ""):
        grouped[_section_name(item[0])].append(item)
    chunks = []
    for name in _SECTION_ORDER:
        rows = grouped[name]
        if not rows:
            continue
        chunks.append(f'<h2 class="section">{esc(name)}</h2>')
        for path, key, kind, value in rows:
            chunks.append(_render_field(path, key, kind, value, fields, defaults))
    return "".join(chunks)


def _collect_fields(obj, prefix):
    found = []
    for key, value in obj.items():
        path = f"{prefix}.{key}" if prefix else key
        kind = field_kind(path, value)
        if kind == "section":
            found.extend(_collect_fields(value, path))
        else:
            found.append((path, key, kind, value))
    return found


def _section_name(path):
    top = path.split(".", 1)[0]
    if top == "layout":
        return "Mise en page"
    if top == "accessories_column":
        return "Accessoires"
    if top == "transit":
        return "Transport"
    if top in _METEO_KEYS:
        return "Météo"
    if top in _AMBIANCE_KEYS:
        return "Ambiance"
    if top in _AFFICHAGE_KEYS:
        return "Affichage"
    return "Autres"


def _submitted_text(path, kind, value, fields):
    if fields is not None and path in fields:
        return fields[path]
    return format_value(kind, value)


def _lookup_default(path, defaults):
    """(présent, valeur). présent est faux si defaults est absent ou sans ce chemin."""
    if not isinstance(defaults, dict):
        return False, None
    try:
        return True, config_file.value_at(defaults, path)
    except KeyError:
        return False, None


def _is_modified(path, kind, value, fields, defaults):
    found, default_value = _lookup_default(path, defaults)
    if not found:
        return False
    if kind == "password":
        typed = fields.get(path, "") if fields else ""
        if typed:
            return True
        return value != default_value
    if fields is not None and path in fields:
        return fields[path] != format_value(field_kind(path, default_value), default_value)
    return value != default_value


def _render_field(path, key, kind, value, fields, defaults):
    raw = _submitted_text(path, kind, value, fields)
    name = f'name="v:{esc(path)}"'
    found, default_value = _lookup_default(path, defaults)
    if isinstance(defaults, dict) and not found:
        modified = True
        default_text = None
        show_reset = False
    else:
        modified = _is_modified(path, kind, value, fields, defaults)
        show_reset = True
        if kind == "password":
            default_text = None
        elif found:
            default_text = format_value(field_kind(path, default_value), default_value)
        else:
            default_text = format_value(kind, value)
    if kind == "bool":
        checked = " checked" if raw == "true" else ""
        control = (
            '<span class="switch">'
            f'<input type="hidden" {name} value="false">'
            f'<input type="checkbox" {name} value="true"{checked}>'
            '<span class="knob"></span>'
            "</span>"
        )
    elif kind == "password":
        control = (
            '<span class="secret-field">'
            f'<input type="password" {name} value="" autocomplete="new-password" '
            'spellcheck="false" placeholder="Laisser vide pour conserver la clé actuelle.">'
            f'<button type="button" class="eye" aria-label="Afficher la clé">{_EYE}</button>'
            "</span>"
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
        try:
            pct = max(0.0, min(100.0, round(float(raw) * 100, 2)))
        except ValueError:
            pct = 0.0
        control = (
            '<span class="slider">'
            f'<input type="range" {name} min="0" max="1" step="0.01" value="{esc(raw)}" '
            f'style="--pct: {pct:g}%">'
            f'<input type="number" class="unit" min="0" max="1" step="0.01" value="{esc(raw)}">'
            "</span>"
        )
    elif kind == "color" and re.fullmatch(r"#[0-9a-fA-F]{6}", raw.strip()):
        shown = raw.strip().upper()
        control = (
            '<span class="color-field">'
            f'<input type="color" {name} value="{esc(raw.strip())}">'
            f'<input type="text" class="hex" value="{esc(shown)}" spellcheck="false" maxlength="7">'
            "</span>"
        )
    elif kind == "json":
        rows = min(16, max(4, raw.count("\n") + 1))
        control = (
            f'<textarea {name} rows="{rows}" spellcheck="false">{esc(raw)}</textarea>'
            '<span class="json-tag">JSON</span>'
        )
    elif kind == "text" and key == "city":
        control = (
            '<span class="text-field">'
            f'<input type="text" {name} value="{esc(raw)}" spellcheck="false">'
            f'<span class="pin">{_PIN}</span>'
            "</span>"
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
    classes = ["row"]
    if kind == "json":
        classes.append("json")
    if modified:
        classes.append("modified")
    attrs = (
        f'class="{" ".join(classes)}" data-path="{esc(path)}" data-kind="{esc(kind)}" '
        f'data-initial-modified="{"1" if modified else "0"}"'
    )
    if default_text is not None:
        attrs += f' data-default="{esc(default_text)}"'
    reset_html = ""
    flag = ""
    if show_reset:
        reset_html = (
            '<button type="button" class="reset" '
            'aria-label="Revenir à la valeur par défaut" '
            'title="Revenir à la valeur par défaut">↺</button>'
        )
        flag = (
            f'<input type="hidden" class="reset-flag" name="reset:{esc(path)}" value="">'
        )
    return (
        f"<div {attrs}>"
        f'<div class="name"><span class="mod-dot" title="Valeur différente du défaut"></span>'
        f"<span>{esc(key)}</span>{_help_button(path, key)}{reset_html}</div>"
        f'<div class="control">{flag}{control}</div>'
        "</div>"
    )


def _help_button(path, key):
    text = _field_help(path, key)
    if not text:
        return ""
    return (
        '<span class="help">'
        '<button type="button" class="help-btn" aria-label="Aide">?</button>'
        f'<span class="help-pop" role="tooltip">{esc(text)}</span>'
        "</span>"
    )


def _field_help(path, key):
    return HELP.get(path) or HELP.get(key, "")


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
        defaults, config, load_error = load_layers()
        if load_error:
            self.send_html(200, render_page(None, notice=load_error, error=True))
            return
        self.send_html(200, render_page(config, defaults=defaults))

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
            action, fields, resets = parse_form(body)
        except UnicodeDecodeError:
            self.send_html(
                400, render_page(None, notice="Encodage de la requête illisible.", error=True)
            )
            return
        if action == "restart":
            ok, message = restart_service()
            defaults, config, load_error = load_layers()
            self.send_html(
                200,
                render_page(
                    config,
                    fields=fields,
                    notice=load_error or message,
                    error=(not ok) or bool(load_error),
                    defaults=defaults,
                ),
            )
            return
        if action != "save":
            defaults, config, load_error = load_layers()
            self.send_html(
                200,
                render_page(
                    config,
                    fields=fields,
                    notice=load_error or "Action inconnue.",
                    error=True,
                    defaults=defaults,
                ),
            )
            return
        defaults, config, load_error = load_layers()
        if load_error:
            self.send_html(200, render_page(None, notice=load_error, error=True))
            return
        built, errors = build_config(config, fields, defaults=defaults, resets=resets)
        if errors:
            self.send_html(
                200,
                render_page(config, fields=fields, errors=errors, defaults=defaults),
            )
            return
        existed = CONFIG_PATH.is_file()
        try:
            save_config(config_file.overrides_only(defaults, built))
        except (OSError, ValueError, TypeError) as exc:
            self.send_html(
                200,
                render_page(
                    config,
                    fields=fields,
                    errors=[f"Écriture impossible : {exc}"],
                    defaults=defaults,
                ),
            )
            return
        saved_defaults, saved, saved_error = load_layers()
        self.send_html(
            200,
            render_page(
                saved if saved_error is None else config,
                notice=(
                    saved_error
                    or (
                        "Enregistré. "
                        + ("Copie précédente : config.json.bak. " if existed else "")
                        + "Redémarrer le service pour appliquer."
                    )
                ),
                error=bool(saved_error),
                defaults=saved_defaults if saved_error is None else defaults,
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

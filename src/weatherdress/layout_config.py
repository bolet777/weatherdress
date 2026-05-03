"""
Paramètres de mise en page (personnage + bloc météo).
Toute clé peut être surchargée via `layout` dans config.json.
"""

DEFAULT_LAYOUT = {
    # Centre horizontal du personnage (0 = gauche, 1 = droite)
    "character_center_x_pct": 0.28,
    # Décalage vertical du centre du personnage vs milieu écran (px)
    "character_center_y_offset_px": -6,
    # Taille max du sprite (fractions de l’écran)
    "character_max_width_pct": 0.42,
    "character_max_height_pct": 0.84,
    # Bloc météo : "after_character" = à droite du sprite, en haut ;
    # "screen_right" = bord droit, centré verticalement
    "weather_mode": "after_character",
    # Marge droite réservée (fraction de la largeur) pour le texte / le wrap
    "weather_screen_right_margin_pct": 0.04,
    # Espace (px) entre bord droit du sprite et début du texte
    "weather_gap_after_character_px": 12,
    # Hauteur du 1er texte météo : fraction écran depuis le haut (0–1)
    "weather_top_pct": 0.07,
    # Décalage vertical du bloc météo et des cartes transport en dessous (négatif = remonter)
    "weather_transit_vertical_offset_px": -28,
    # Tailles de police (min / max en px, bornées par l’écran)
    "weather_temp_font_min": 52,
    "weather_temp_font_max": 102,
    "weather_desc_font_min": 22,
    "weather_desc_font_max": 38,
    "weather_note_font_min": 15,
    "weather_note_font_max": 26,
}


def effective_layout(config):
    """Fusionne config['layout'] (dict) avec les défauts."""
    raw = config.get("layout")
    if not isinstance(raw, dict):
        return dict(DEFAULT_LAYOUT)
    merged = dict(DEFAULT_LAYOUT)
    merged.update(raw)
    return merged

# Mise en page (personnage + texte météo)

Tout se règle dans **`config.json`** sous la clé **`layout`** (objet JSON optionnel). Les valeurs absentes sont complétées par les défauts du fichier `layout_config.py`.

## Exemple

```json
"layout": {
  "character_center_x_pct": 0.26,
  "weather_top_pct": 0.06,
  "weather_temp_font_min": 58,
  "weather_temp_font_max": 110
}
```

## Personnage

| Clé | Rôle |
|-----|------|
| `character_center_x_pct` | Position horizontale du **centre** du sprite (0 = bord gauche, 1 = droite). Défaut `0.28`. |
| `character_center_y_offset_px` | Décalage vertical du centre par rapport au milieu de l’écran (pixels, négatif = plus haut). Défaut `-6`. |
| `character_max_width_pct` | Largeur max du sprite en fraction de la largeur d’écran. Défaut `0.42`. |
| `character_max_height_pct` | Hauteur max du sprite en fraction de la hauteur d’écran. Défaut `0.84`. |

## Texte météo

| Clé | Rôle |
|-----|------|
| `weather_mode` | **`after_character`** : bloc à droite du personnage, ancré en haut (zone type « placeholder » au centre-droit). **`screen_right`** : aligné au bord droit, centré verticalement. |
| `weather_gap_after_character_px` | Espace entre le bord droit du personnage et le début du texte (mode `after_character`). |
| `weather_top_pct` | Hauteur du **premier** texte (température) en fraction de la hauteur d’écran depuis le **haut** (0–1). Ex. `0.07` ≈ 7 % du haut. |
| `weather_screen_right_margin_pct` | Marge droite réservée (fraction de la largeur) pour ne pas coller au bord et pour le retour à la ligne. |

### Tailles de police

Chaque taille est choisie entre **min** et **max** (pixels), en restant cohérente avec la hauteur d’écran :

- `weather_temp_font_min` / `weather_temp_font_max` — température (gras).
- `weather_desc_font_min` / `weather_desc_font_max` — description météo.
- `weather_note_font_min` / `weather_note_font_max` — ligne de prévision (ex. « pluie dans 8H »).

Pour agrandir le texte : augmentez surtout **min** et **max** de la température (et éventuellement de la description).

## Réglage rapide « comme le placeholder jaune »

1. Gardez **`weather_mode": "after_character"`** (défaut).
2. Montez **`weather_top_pct`** (ex. `0.05`–`0.10`) pour monter ou descendre le bloc.
3. Ajustez **`weather_gap_after_character_px`** pour coller ou éloigner le texte du personnage.
4. Déplacez le personnage avec **`character_center_x_pct`** si le texte chevauche le sprite.

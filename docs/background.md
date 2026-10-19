# Fonds d’écran météo

Les images dans `images/backgrounds/` sont choisies selon la **réponse OpenWeatherMap** (code condition `weather[0].id`, puis le suffixe jour/nuit de l’icône `weather[0].icon`).

## Fichier de mapping

Tout est centralisé dans **`images/backgrounds/background_map.json`** :

- **`keys_to_file`** : associe une **clé logique** (nom stable, `snake_case`) au **nom de fichier** PNG. Pour ajouter une image, placez le fichier dans `images/backgrounds/` et ajoutez ou réutilisez une entrée ici.
- **`rules`** : liste **ordonnée** de règles ; la **première** qui correspond gagne.
  - **`condition_id`** : code exact OpenWeatherMap (voir [Weather conditions](https://openweathermap.org/weather-conditions)).
  - **`condition_id_range`** : plage inclusive `[min, max]` (ex. orages `200`–`232`).
  - **`key`** : clé dans `keys_to_file`.
- **`default_key`** : clé utilisée si aucune règle ne correspond (icône inattendue, etc.).

Si l’icône finit par `n` et que `{clé}_night` existe dans `keys_to_file`, cette clé de nuit est utilisée (`rain` → `rain_night`, ciel dégagé `800` → `sunny_night`). Sinon la clé de jour est conservée. Une icône sans suffixe `n` reste sur la clé de jour (`800` → `sunny`).

De décembre à mars (date locale), la première clé présente gagne : la nuit `{clé}_winter_night`, `{clé}_night`, `{clé}` ; le jour `{clé}_winter`, puis `{clé}`. Une variante de jour n’est pas utilisée la nuit. Hors de ces mois, seul le repli `_night` s’applique.

Modifier ce JSON **ne nécessite pas** de toucher au code Python : redémarrer l’app suffit (le fichier est relu quand sa date de modification change).

## Désactiver les images

Dans `config.json` :

```json
"use_weather_background": false
```

Le fond redevient la couleur `background_color` (comme avant).

## Rendu

L’image est mise à l’échelle en mode **« cover »** : elle remplit tout l’écran, le surplus est rogné au centre.

Quand une image météo est affichée (`use_weather_background` et fichier résolu), le **médaillon circulaire** et le fond uni derrière ne sont **pas** dessinés : le personnage et la ligne météo en bas sont directement sur la photo ; le texte météo est sur une **pastille** semi-transparente (coins arrondis) pour rester lisible sans contour pixelisé.

### Ambiance jour / nuit et ciel (optionnel)

Avec **`use_ambient_weather_background`: `true`**, l’app calcule une **couleur de remplissage** sous la photo et l’**opacité** de cette photo à partir des timestamps **lever / coucher du soleil** fournis par OpenWeatherMap (`sys.sunrise`, `sys.sunset`, UTC) et du **pourcentage de nuages**. Sans ces champs (réponse atypique), repli sur le suffixe jour/nuit de l’icône (`d` / `n`) puis sur l’heure locale.

- **`weather_background_alpha`** reste le **plafond de base** (0–1 ou 0–255) ; l’ambiance peut réduire l’opacité la nuit ou par temps très couvert.
- **`ambient_twilight_minutes`** : largeur des transitions autour du lever et du coucher (défaut 45).
- **`ambient_min_day_brightness`** : luminosité minimale en plein jour quand les nuages sont à 100 % (évite un midi entièrement noir).
- **`ambient_night_bg`**, **`ambient_day_clear_bg`**, **`ambient_day_overcast_bg`** : couleurs cibles `[R,G,B]` ou `"#rrggbb"` (voir `config.default.json`).

Sans cette option, le comportement reste : `background_color` sous la photo et `weather_background_alpha` fixe.

### Rectangle noir derrière le personnage

Ce n’est **pas** dessiné par l’app : en général les PNG du dossier `images/characters/` (ou accessoires) ont un **fond noir opaque** au lieu d’une **transparence** (canal alpha). Le fond météo est bien en dessous, mais le sprite le recouvre.

**Correctif recommandé :** réexporter les images en PNG avec transparence autour du personnage.

**Paliatif :** dans `config.json`, définir par exemple `"character_colorkey": [0, 0, 0]` pour rendre le **noir pur** transparent. À n’utiliser que si le dessin n’a **pas** de noir utile (vêtements, cheveux), sinon ces zones disparaîtront aussi.

## Liste d’idées (conditions ↔ visuels)

Référence pour nommer ou regrouper vos assets :

1. Soleil / clair  
2. Nuageux léger  
3. Couvert / gris  
4. Pluie légère / bruine  
5. Pluie forte / orage  
6. Neige / verglas  
7. Brouillard / brume / poussière  

Les clés par défaut (`sunny`, `partly_cloudy`, `overcast`, `drizzle`, `rain`, `thunderstorm`, `snow`, `fog`, `dust`, et leurs variantes `_night`) peuvent être renommées dans `keys_to_file` tant que vous gardez les mêmes `key` dans `rules`.

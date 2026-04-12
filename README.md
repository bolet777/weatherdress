# WeatherDress

Affiche un personnage habillé selon la météo actuelle. Conçu pour un Raspberry Pi avec écran 7" (800×480).

---

## Prérequis

- Python 3.10+
- Clé API [OpenWeatherMap](https://openweathermap.org/api) (plan gratuit suffit)
- Pygame 2.x, requests

---

## Setup local (Mac)

```bash
# 1. Cloner le dépôt
git clone <repo> weatherdress && cd weatherdress

# 2. Installer les dépendances
make install

# 3. Créer config.json
cp config.example.json config.json
# Renseigner api_key et city dans config.json
# Sur Mac : mettre "fullscreen": false pour une fenêtre (tests), true sur le Pi

# 4. Ajouter les images (voir section Images ci-dessous)

# 5. Lancer
make run
```

Appuyer sur `Échap` pour quitter.

---

## Images attendues

### Personnages — `images/characters/`

Format : `{condition}_{genre}{numéro}.png`

| Condition  | Températures          |
|------------|-----------------------|
| `verycold` | < -9°C                |
| `cold`     | -9°C à 17°C           |
| `normal`   | 17°C à 25°C           |
| `hot`      | 25°C à 28°C           |
| `veryhot`  | ≥ 28°C                |
| `snow`     | neige détectée        |

Exemples : `cold_woman1.png`, `normal_man1.png`, `snow_woman1.png`

### Accessoires — `images/accessories/`

| Fichier          | Déclencheur                              |
|------------------|------------------------------------------|
| `umbrella.png`   | Pluie prévue                             |
| `sunglasses.png` | Peu nuageux + entre 7h et 17h            |
| `hat.png`        | Grand soleil (9h–16h) ou ≥ 28°C         |
| `boots.png`      | Neige ou pluie forte (> 5 mm/h)         |
| `scarf.png`      | Temp < 5°C ou vent > 30 km/h            |

Les images doivent être en PNG avec transparence (canal alpha).
Elles sont superposées sur le personnage — prévoir un fond transparent.

---

## Setup Raspberry Pi

```bash
# Sur le Pi, dans le répertoire du projet :
cp config.example.json config.json
nano config.json   # renseigner api_key et city

bash install.sh
```

Le service démarre automatiquement au boot.

Commandes utiles :
```bash
sudo systemctl status weatherdress
sudo systemctl restart weatherdress
journalctl -u weatherdress -f
```

---

## Déploiement depuis le Mac

```bash
make deploy HOST=pi@raspberrypi.local
```

Cela synchronise les fichiers (hors `config.json`) et redémarre le service.

---

## Tests

```bash
make test
```

---

## config.json

| Clé                | Description                                      |
|--------------------|--------------------------------------------------|
| `api_key`          | Clé OpenWeatherMap                               |
| `fullscreen`       | `true` plein écran (Pi), `false` fenêtre (tests Mac) |
| `background_color` | Fond : `[R,G,B]` ou `"#rrggbb"` ; optionnel. Le texte UI s’ajuste (clair sur fond sombre). |
| `city`             | Ville (ex: `"Montreal,CA"`)                      |
| `language`         | Optionnel : défaut **`fr`**. Interface + paramètre `lang` OpenWeatherMap (`"en"`, `"de"`, … — voir `locale/` et [codes API](https://openweathermap.org/current#multi)) |
| `units`            | `"metric"` (Celsius) ou `"imperial"`             |
| `screen_width`     | Largeur écran en pixels                          |
| `screen_height`    | Hauteur écran en pixels                          |
| `refresh_minutes`  | Intervalle de rafraîchissement météo             |
| `forecast_hours`   | Horizon de prévision pour les accessoires futurs |
| `forecast_step_hours` | Granularité des tranches (3h sur l'API gratuite) |
| `identity_on_each_refresh` | `true` / `false` : nouveau couple genre / variante à chaque fetch météo ou identité fixe. **Si la clé est absente** et `refresh_minutes` ≤ 1, la rotation est **activée** (pratique pour les tests) ; sinon identité fixe au démarrage (comportement Pi). |
| `character_variant_max` | Borne supérieure du numéro tiré au hasard (1…N, défaut **6**) |

---

## Personnages : variantes et repli automatique

- Les types **très froid / très chaud** du moteur météo utilisent les sprites **`cold_*`** et **`hot_*`** (pas de fichiers `verycold` / `veryhot` requis).
- Si `normal_woman5.png` est absent, l’app charge **`normal_woman4`** … jusqu’à **`…1`** dès qu’un fichier existe, ce qui permet d’ajouter les images progressivement.

---

## Langues et traductions

- `language` dans `config.json` charge `locale/<code>.json` (clés manquantes complétées par `locale/en.json`). Sans cette clé, la langue par défaut est le **français** ; mettre `"language": "en"` pour l’anglais.
- Les **descriptions météo** (nuages, pluie, etc.) viennent d’OpenWeatherMap dans la même langue lorsque l’API la supporte ([liste des codes](https://openweathermap.org/current#multi)).
- Pour ajouter une langue : copier `locale/en.json` vers `locale/de.json` (par ex.), traduire les valeurs, puis `"language": "de"`.

---

## Structure du projet

```
weatherdress/
├── main.py              # point d'entrée
├── i18n.py              # chargement des traductions
├── locale/              # fichiers JSON par langue (fr, en, …)
├── weather.py           # appel OpenWeatherMap
├── outfit.py            # logique tenue et accessoires
├── character_assets.py  # résolution des PNG personnage (repli numéro)
├── identity_config.py   # règle rotation d’identité (refresh / option)
├── display.py           # rendu pygame
├── config.json          # (non commité — créer depuis config.example.json)
├── config.example.json  # référence
├── weatherdress.service # service systemd
├── install.sh           # setup Pi
├── uninstall.sh         # suppression service Pi
├── deploy.sh            # déploiement depuis Mac
├── Makefile
├── requirements.txt
├── requirements-dev.txt
├── tests/
│   ├── test_outfit.py
│   ├── test_i18n.py
│   ├── test_character_assets.py
│   └── test_identity_config.py
└── images/
    ├── characters/
    └── accessories/
```

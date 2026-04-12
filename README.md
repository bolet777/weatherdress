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
| `units`            | `"metric"` (Celsius) ou `"imperial"`             |
| `screen_width`     | Largeur écran en pixels                          |
| `screen_height`    | Hauteur écran en pixels                          |
| `refresh_minutes`  | Intervalle de rafraîchissement météo             |
| `forecast_hours`   | Horizon de prévision pour les accessoires futurs |
| `forecast_step_hours` | Granularité des tranches (3h sur l'API gratuite) |

---

## Structure du projet

```
weatherdress/
├── main.py              # point d'entrée
├── weather.py           # appel OpenWeatherMap
├── outfit.py            # logique tenue et accessoires
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
│   └── test_outfit.py
└── images/
    ├── characters/
    └── accessories/
```

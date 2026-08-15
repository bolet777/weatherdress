# WeatherDress

Affiche un personnage habillé selon la météo actuelle. Conçu pour un Raspberry Pi avec écran 7" (800×480).

---

## Prérequis

- Python 3.10+
- Clé API [OpenWeatherMap](https://openweathermap.org/api) (plan gratuit suffit)
- Pygame 2.x, requests

---

## Lancer sous macOS

Le projet tourne en **Python** avec **Pygame** (fenêtre graphique). Il faut l’exécuter depuis le **Terminal** (ou un terminal intégré à l’IDE), pas en SSH sans affichage graphique.

### Prérequis sur le Mac

- **Python 3.10 ou plus récent** et **pip**. Vérifier : `python3 --version`  
  Si besoin : installer [Python pour macOS](https://www.python.org/downloads/macos/) ou via Homebrew : `brew install python`.
- **Git** et **make** (souvent déjà présents). Les outils de ligne de commande Xcode : `xcode-select --install` si `git` ou `make` est introuvable.
- **Clé API** OpenWeatherMap (voir la section **Prérequis** plus haut).

### Installation et configuration

```bash
# 1. Cloner le dépôt
git clone <repo> weatherdress && cd weatherdress

# 2. (Optionnel) Environnement virtuel — recommandé pour isoler les paquets
python3 -m venv .venv
source .venv/bin/activate   # à refaire à chaque nouveau terminal

# 3. Dépendances Python
make install
# équivalent : pip install -r requirements-dev.txt
```

Créer `config.json` à partir du modèle, renseigner la clé et la ville :

```bash
cp config.example.json config.json
# Éditer config.json : api_key, city, etc.
```

**Pour le développement sur Mac**, mettre `"fullscreen": false` dans `config.json` pour obtenir une **fenêtre** redimensionnable au lieu du plein écran (sur le Raspberry Pi, on garde en général `"fullscreen": true`).

Ajouter les images sous `images/` (voir [Images attendues](#images-attendues) ci-dessous).

### Lancer l’application

Depuis la racine du dépôt (`weatherdress/`) :

```bash
make run
```

(`make run` définit `PYTHONPATH=src` et lance `python3 -m weatherdress.main`.)

Ou le script dédié macOS (active `.venv` s’il existe, puis lance le module avec `PYTHONPATH=src`) :

```bash
./scripts/launch_macos.sh
```

Équivalent manuel depuis la racine du dépôt :

```bash
PYTHONPATH=src python3 -m weatherdress.main
```

**Quitter** : touche `Échap` lorsque la fenêtre Pygame a le focus.

### Dépannage rapide (macOS)

- **`python: command not found`** : utiliser `python3` / `pip3`, ou activer le venv (`source .venv/bin/activate`).
- **Erreur à l’import ou au lancement de Pygame** : s’assurer d’avoir installé les dépendances dans le même interpréteur que celui utilisé pour lancer (`which python3`).
- **Fenêtre invisible ou plantage au démarrage** : lancer depuis une session macOS locale avec un écran connecté (pas uniquement SSH sans forwarding graphique).

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
| `umbrella.png`   | Pluie (mm > 0 ou codes OWM pluie/bruine/orage), sans neige |
| `sun_screen.png` | Ciel sec, clair (`clouds` < 20), de jour (6–19 h ou lever/coucher) |
| `sunglasses.png` | Ciel sec, 6h–17h, ciel clair (`clouds` < 20), pas nuageux/couvert (≥ 40 %, codes 803/804, icône 04) |
| `beanie.png`     | Neige (`snow` > 0) ou froid (`temp` < 7°C) |
| `hat.png`        | Ciel sec, 7h–17h : ciel clair (`clouds` < 20) ou forte chaleur (`temp` ≥ 28°C) si `clouds` < 30 |
| `cap.png`        | Ciel sec, 9h–17h, légèrement nuageux (`clouds` 20–29) et `temp` < 28°C |
| `boots.png`      | Neige : `snow` > 0                       |
| `rain_boots.png` | Pluie forte : > 3 mm/h (actuel 1 h ; prévision 3 h ÷ 3), sans neige |
| `crampons.png`   | Code **511** ; ou pluie (mm ou code) sans neige et `temp` ≤ 2°C |
| `scarf.png`      | `temp` < 5°C, ou vent > 30 km/h avec `temp` ≤ 18°C |

Les images doivent être en PNG avec transparence (canal alpha).
Elles sont superposées sur le personnage — prévoir un fond transparent.

---

## Setup Raspberry Pi

```bash
# Sur le Pi, dans le répertoire du projet :
cp config.example.json config.json
nano config.json   # renseigner api_key et city

bash scripts/install.sh
```

Le service démarre automatiquement au boot. Le unit systemd est **généré** à partir de `packaging/weatherdress.service.in` avec le répertoire courant du clone (`WorkingDirectory`, `PYTHONPATH=…/src`), l’utilisateur graphique (`User`, `XAUTHORITY`) et `python3 -m weatherdress.main`. Lancer l’installation **depuis le répertoire du clone** (après `cd` dans ce dossier). En général : `sudo bash scripts/install.sh` depuis le compte qui possède le clone (ex. `weather`) — `SUDO_USER` sert alors à remplir `User=`. Si vous installez en root sans `SUDO_USER`, définir explicitement `WEATHERDRESS_USER=weather` (ou l’utilisateur qui lance la session X11).

**Le service `weatherdress` ne fait pas de `git pull`.** Il lance uniquement l’application (`python3 -m weatherdress.main`), redémarre en cas de crash (`Restart=on-failure`) et repart au boot. Aucun timer ni cron n’est installé par `install.sh` : le dépôt sur le Pi **ne se met pas à jour tout seul** tant que vous n’avez pas choisi une des options ci‑dessous.

### Mettre à jour le code sur le Pi

| Méthode | Quand l’utiliser |
|--------|-------------------|
| **`make deploy`** depuis le Mac | Vous poussez sur `main` et vous déployez à la demande (SSH → `scripts/launch.sh`). |
| **`bash scripts/launch.sh`** sur le Pi | Même chose qu’un deploy, en SSH ou sur la console du Pi (dans le clone : `git pull origin main` + restart). |
| **`bash scripts/gitsync.sh`** sur le Pi | Sync **automatique** seulement si **vous** planifiez le script (cron, timer systemd, etc.) — voir ci‑dessous. |

`gitsync.sh` se contente d’aller dans le clone (`~/weatherdress` par défaut, ou `WEATHERDRESS_REPO`) puis d’appeler `launch.sh`. Il n’est **pas** exécuté par le service `weatherdress`.

Exemple cron sur le compte qui possède le clone (adapter le chemin utilisateur) :

```bash
crontab -e
# toutes les 6 heures :
0 */6 * * * /home/weather/weatherdress/scripts/gitsync.sh >>/home/weather/weatherdress-gitsync.log 2>&1
```

En cron, `sudo systemctl restart weatherdress` exige en général une règle **sudoers** sans mot de passe pour cette commande, faute de quoi le pull réussit mais le restart échoue.

### Mise à jour d’un Pi déjà configuré (après `git pull`)

Après réception du nouveau layout (`src/`, `scripts/`, `packaging/`), exécuter une fois depuis le clone :

```bash
cd ~/weatherdress && git pull
bash scripts/install.sh
```

Cela régénère le fichier service (chemins + utilisateur) et recharge systemd. À défaut : relancer `bash scripts/install.sh` depuis le clone, ou régénérer à la main avec le même `sed` que dans `scripts/install.sh`, puis `sudo systemctl daemon-reload` et `sudo systemctl restart weatherdress`.

Commandes utiles :
```bash
sudo systemctl status weatherdress
sudo systemctl restart weatherdress
journalctl -u weatherdress -f
```

Si les journaux mentionnent `XDG_RUNTIME_DIR is invalid or not set` : le service généré définit `XDG_RUNTIME_DIR=/run/user/<uid>` et un `ExecStartPre` crée ce répertoire avec les bons droits. Après mise à jour du dépôt, relancer `bash scripts/install.sh` pour régénérer le unit. En complément (kiosk sans session graphique au boot) : `sudo loginctl enable-linger <utilisateur_du_service>` pour que logind maintienne le runtime utilisateur.

---

## Déploiement depuis le Mac

```bash
make deploy HOST=weather@weatherdress.local
```

Connexion SSH au Pi, exécution de `~/weatherdress/scripts/launch.sh` : `git pull origin main` puis redémarrage du service systemd. Pour un Pi qui se met à jour sans Mac, voir **`scripts/gitsync.sh`** et la section « Mettre à jour le code sur le Pi ».

`weather.local` est un **exemple** : il faut le nom mDNS réel du Pi (souvent `raspberrypi.local` si inchangé) ou, si macOS n’arrive pas à résoudre `*.local` (`Could not resolve hostname`), l’**adresse IP** du Pi sur le LAN, par ex. `make deploy HOST=weather@192.168.1.42`.

Le dépôt sur le Pi doit contenir **`scripts/launch.sh`** (même branche que sur le Mac, typiquement `main`). Sinon, une première fois en SSH : `cd ~/weatherdress && git pull origin main`.

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
| `use_weather_background` | `true` (défaut) : image de fond selon la météo (`images/backgrounds/` + `background_map.json`). `false` : uniquement `background_color`. Voir `docs/background.md`. |
| `weather_background_alpha` | Opacité de la photo de fond (0–1 ou 0–255). Avec `use_ambient_weather_background`, sert de plafond de base avant assombrissement jour/nuit / nuages. |
| `use_ambient_weather_background` | `false` (défaut) : inchangé. `true` : couleur sous la photo et alpha dérivés du lever/coucher de soleil (API) et du pourcentage de nuages ; voir `docs/background.md`. |
| `ambient_twilight_minutes` | Demi-largeur des transitions aube/crépuscule (défaut **45**). |
| `ambient_min_day_brightness` | Plancher de luminosité de jour quand le ciel est couvert, 0–1 (défaut **0.22**). |
| `ambient_night_bg`, `ambient_day_clear_bg`, `ambient_day_overcast_bg` | Couleurs `[R,G,B]` ou `"#rrggbb"` pour le dégradé sous la photo (nuit / jour clair / jour nuageux). |
| `character_colorkey` | Optionnel : `[R,G,B]` pour rendre cette couleur transparente sur les sprites personnage/accessoires (ex. fond noir `[0,0,0]` si les PNG n’ont pas d’alpha). Risque si le dessin utilise la même couleur. |
| `layout`           | Objet optionnel : position du personnage, placement du texte météo (`after_character` = à droite du sprite, en haut ; `screen_right` = bord droit), tailles min/max des polices. Détail : `docs/layout.md`. |
| `city`             | Ville (ex: `"Montreal,CA"`)                      |
| `language`         | Optionnel : défaut **`fr`**. Interface + paramètre `lang` OpenWeatherMap (`"en"`, `"de"`, … — voir `locale/` et [codes API](https://openweathermap.org/current#multi)) |
| `units`            | `"metric"` (Celsius) ou `"imperial"`             |
| `screen_width`     | Largeur fenêtre en pixels (`fullscreen`: false)  |
| `screen_height`    | Hauteur fenêtre en pixels ; en plein écran, résolution native du moniteur |
| `refresh_minutes`  | Intervalle de rafraîchissement météo             |
| `forecast_hours`   | Horizon de prévision pour les accessoires futurs |
| `forecast_step_hours` | Granularité des tranches (3h sur l'API gratuite) |
| `identity_on_each_refresh` | `true` : rotation à chaque fetch. `false` : identité fixe si `refresh_minutes` ≥ 60 (Pi) ou ≤ 1 (tests météo rapides) ; avec un refresh intermédiaire (ex. 5 min), le personnage **tourne quand même** à chaque fetch. **Clé absente** : rotation si `refresh_minutes` ≤ 5, sinon fixe au démarrage. |
| `character_variant_max` | Optionnel, **clip** `n ≤ max` après lecture des PNG dans `images/characters/` pour le préfixe météo courant. Sans la clé ou ≤ 0 : tous les fichiers présents sont éligibles. |
| `transit` | Optionnel : bandeau bas STM (bus temps réel + métro au prochain horaire GTFS). Requiert au minimum `gtfs_url` et `metro_station`. Clés utiles : `stm_api_key` (Open Data STM, pour le flux tripUpdates bus), `bus_stops` (`stop_id` → libellé), `metro_route_id`, `metro_directions` (libellés : clés = `trip_headsign` exact du GTFS), `transit_refresh_seconds`. Le GTFS est mis en cache sous `cache/gtfs_stm.zip` ; l’index métro dérivé sous `cache/metro_index.json` (invalidé si le GTFS ou la config métro change). Au démarrage, les cartes bus/métro s’affichent tout de suite (—) ; le bus se met à jour sans attendre l’index métro. |

---

## Personnages : variantes et repli automatique

- Les types **très froid / très chaud** du moteur météo utilisent les sprites **`cold_*`** et **`hot_*`** (pas de fichiers `verycold` / `veryhot` requis).
- **Tirage d’identité** : pour le préfixe courant (`normal` avant la première météo, puis le préfixe dérivé de la température / neige), l’app liste les PNG **`{prefix}_{woman|man}{n}.png`** présents et choisit `n` au hasard dans cette liste. La clé **`character_variant_max`** (> 0) limite ce choix à `n ≤ max` ; absente ou ≤ 0 : toutes les variantes trouvées sur le disque.
- Sans répertoire valide ou sans fichier pour le préfixe / genre : repli sur un entier aléatoire **`1…character_variant_max`** (défaut 6).
- À l’**affichage**, si `normal_woman5.png` est absent, l’app charge **`normal_woman4`** … jusqu’à **`…1`** dès qu’un fichier existe (repli distinct du tirage d’identité).

---

## Langues et traductions

- `language` dans `config.json` charge `locale/<code>.json` (clés manquantes complétées par `locale/en.json`). Sans cette clé, la langue par défaut est le **français** ; mettre `"language": "en"` pour l’anglais.
- Les **descriptions météo** (nuages, pluie, etc.) viennent d’OpenWeatherMap dans la même langue lorsque l’API la supporte ([liste des codes](https://openweathermap.org/current#multi)).
- Pour ajouter une langue : copier `locale/en.json` vers `locale/de.json` (par ex.), traduire les valeurs, puis `"language": "de"`.

---

## Structure du projet

```
weatherdress/
├── src/
│   └── weatherdress/    # package Python (main, display, météo, i18n, …)
├── scripts/
│   ├── install.sh       # setup Pi (dépendances + service systemd)
│   ├── uninstall.sh     # suppression du service sur le Pi
│   ├── launch.sh        # sur le Pi : git pull + restart systemd
│   ├── gitsync.sh       # sur le Pi : wrapper vers launch.sh (ex. cron)
│   └── launch_macos.sh  # sur le Mac : lance l’app (venv si présent)
├── packaging/
│   └── weatherdress.service.in   # modèle ; le .service installé est généré par install.sh
├── locale/              # fichiers JSON par langue (fr, en, …)
├── config.json          # (non commité — créer depuis config.example.json)
├── config.example.json  # référence
├── pytest.ini           # pythonpath = src pour les tests
├── Makefile
├── requirements.txt
├── requirements-dev.txt
├── tests/
│   ├── test_outfit.py
│   ├── test_i18n.py
│   ├── test_layout_config.py
│   ├── test_background_assets.py
│   ├── test_character_assets.py
│   └── test_identity_config.py
└── images/
    ├── backgrounds/     # PNG + background_map.json (mapping météo)
    ├── characters/
    └── accessories/
```

# Éditeur de configuration

Page pour modifier `config.json` depuis le navigateur, pendant que l’application tourne sur le Pi. L’application ne relit pas `config.json` toute seule. Après un enregistrement, redémarrer le service (bouton **Redémarrer**, ou `sudo systemctl restart weatherdress`).

Les champs `api_key` et `stm_api_key` restent vides. Laisser vide conserve la clé déjà enregistrée.

## Réseau domestique

`scripts/install.sh` installe le service `weatherdress-config`. Il lance l’éditeur sur le port **8765**, à l’écoute de toutes les interfaces. Ouvrir :

http://weather.local:8765

Remplacer `weather.local` par le nom mDNS du Pi, ou par son adresse IP.

Le service refuse de démarrer tant que le mot de passe n’existe pas. Le créer **avec le compte qui fait tourner le service** (souvent `weather`), une seule ligne, jamais dans `config.json` :

```bash
mkdir -p ~/.config/weatherdress
printf '%s\n' 'votre-mot-de-passe' > ~/.config/weatherdress/editor_password
chmod 600 ~/.config/weatherdress/editor_password
sudo systemctl restart weatherdress-config
```

Le navigateur demande un identifiant et ce mot de passe. L’identifiant est ignoré.

```bash
sudo systemctl status weatherdress-config
journalctl -u weatherdress-config -f
```

## Tunnel SSH

Pour ne pas laisser passer le mot de passe et les clés en clair sur le Wi-Fi, ouvrir un tunnel vers le service déjà lancé :

```bash
ssh -L 8765:127.0.0.1:8765 weather@weatherdress.local
```

Puis http://127.0.0.1:8765. Le mot de passe du fichier est toujours demandé, parce que le service écoute sur toutes les interfaces.

Sans le service, un lancement manuel n’écoute que sur la machine locale et ne demande pas de mot de passe (libérer le port 8765 avant, avec `sudo systemctl stop weatherdress-config`) :

```bash
cd ~/weatherdress
python3 scripts/config_editor.py
```

## Redémarrage sans mot de passe

Le bouton **Redémarrer** exécute `sudo -n systemctl restart weatherdress`. Sans règle sudoers, sudo refuse et le message s’affiche dans la page.

Sur le Pi, vérifier le chemin de `systemctl` :

```bash
command -v systemctl
```

Puis, pour l’utilisateur qui lance l’éditeur (souvent `weather`) :

```bash
sudo visudo -f /etc/sudoers.d/weatherdress
```

```
weather ALL=(ALL) NOPASSWD: /usr/bin/systemctl restart weatherdress
```

Remplacer `weather` et le chemin si `command -v` donne autre chose que `/usr/bin/systemctl`. `visudo` refuse un fichier invalide. Vérifier avec :

```bash
sudo -n systemctl restart weatherdress
```

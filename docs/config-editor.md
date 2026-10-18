# Éditeur de configuration

Page locale pour modifier `config.json` depuis le Mac pendant que l’application tourne sur le Pi. Le serveur n’écoute que sur `127.0.0.1:8765`.

L’application ne relit pas `config.json` toute seule. Après un enregistrement, redémarrer le service.

## Tunnel SSH

Sur le Mac, une session à laisser ouverte :

```bash
ssh -L 8765:127.0.0.1:8765 weather@weatherdress.local
```

Remplacer l’utilisateur et l’hôte par ceux du Pi (`weather@192.168.1.42` si le nom `.local` ne se résout pas).

## Lancement

Dans cette même session, depuis le clone :

```bash
cd ~/weatherdress
python3 scripts/config_editor.py
```

Ouvrir http://127.0.0.1:8765 dans le navigateur du Mac. Ctrl+C arrête l’éditeur. Le bouton **Enregistrer** copie l’ancien fichier vers `config.json.bak`, puis remplace `config.json`. Le bouton **Redémarrer** relance le service.

## Redémarrage sans mot de passe

Le bouton exécute `sudo -n systemctl restart weatherdress`. Sans règle sudoers, sudo refuse et le message s’affiche dans la page.

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

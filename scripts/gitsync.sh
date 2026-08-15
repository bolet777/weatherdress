#!/usr/bin/env bash
# Mise à jour automatique sur le Pi (cron, timer systemd, etc.).
# Même logique que « make deploy » mais exécuté localement sur le clone.
#
# Exemple cron (toutes les 6 h) :
#   0 */6 * * * /home/weather/weatherdress/scripts/gitsync.sh >>~/weatherdress-gitsync.log 2>&1
#
# Le redémarrage du service utilise sudo : autoriser sans mot de passe pour
# systemctl restart weatherdress (sudoers) si le job tourne sans TTY.
set -euo pipefail

REPO="${WEATHERDRESS_REPO:-$HOME/weatherdress}"

if [ ! -d "$REPO/.git" ]; then
  echo "gitsync: dépôt introuvable : $REPO" >&2
  exit 1
fi

if [ ! -f "$REPO/scripts/launch.sh" ]; then
  echo "gitsync: $REPO/scripts/launch.sh absent — git pull origin main une fois à la main." >&2
  exit 1
fi

cd "$REPO"
exec bash ./scripts/launch.sh

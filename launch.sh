#!/usr/bin/env bash
# Déploiement rapide sur Raspberry Pi : mise à jour git + redémarrage du service.
set -e

is_raspberry_pi() {
  if [ -f /proc/device-tree/model ]; then
    grep -qi raspberry /proc/device-tree/model 2>/dev/null
    return $?
  fi
  return 1
}

if ! is_raspberry_pi; then
  echo "launch.sh : réservé au Raspberry Pi (/proc/device-tree/model)."
  echo "Aucune action sur cette machine."
  exit 0
fi

git pull origin main
sudo systemctl restart weatherdress

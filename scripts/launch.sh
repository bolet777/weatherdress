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

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

git pull origin main

# Page d'erreur ou téléchargement coupé : le fichier n'est pas un zip, et
# l'appli le gardait 7 jours. On le retire pour forcer un nouveau téléchargement.
GTFS_ZIP="$ROOT/cache/gtfs_stm.zip"
if [ -f "$GTFS_ZIP" ] && ! python3 -c 'import sys, zipfile; sys.exit(0 if zipfile.is_zipfile(sys.argv[1]) else 1)' "$GTFS_ZIP"; then
  echo "launch.sh : cache GTFS invalide, suppression."
  rm -f "$GTFS_ZIP" "$ROOT/cache/gtfs_stm.zip.part" "$ROOT/cache/metro_index.json"
fi

sudo systemctl restart weatherdress

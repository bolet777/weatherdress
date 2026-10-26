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

# Archive illisible, incomplète ou sans les fichiers GTFS : on la retire
# pour que le redémarrage retélécharge, au lieu de la garder 7 jours.
GTFS_ZIP="$ROOT/cache/gtfs_stm.zip"
if [ -f "$GTFS_ZIP" ] && ! PYTHONPATH="$ROOT/src${PYTHONPATH:+:$PYTHONPATH}" python3 - "$GTFS_ZIP" << 'PY'
import sys
try:
    from weatherdress.transit import gtfs_archive_ok
except Exception as exc:
    print(f"launch.sh : vérification GTFS ignorée ({exc})", file=sys.stderr)
    sys.exit(0)
sys.exit(0 if gtfs_archive_ok(sys.argv[1]) else 1)
PY
then
  echo "launch.sh : cache GTFS invalide, suppression."
  rm -f "$GTFS_ZIP" "$ROOT/cache/gtfs_stm.zip.part" "$ROOT/cache/metro_index.json"
fi

sudo systemctl restart weatherdress

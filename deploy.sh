#!/usr/bin/env bash
# Usage : ./deploy.sh pi@raspberrypi.local
# Synchronise le projet sur le Pi et redémarre le service.
set -e

TARGET="${1:-}"
if [ -z "$TARGET" ]; then
    echo "Usage : $0 user@hote"
    exit 1
fi

REMOTE_DIR="/home/pi/weatherdress"

echo "==> Synchronisation vers $TARGET:$REMOTE_DIR ..."
rsync -av --exclude='.git' --exclude='__pycache__' --exclude='.env' \
    --exclude='config.json' \
    ./ "$TARGET:$REMOTE_DIR/"

echo "==> Redémarrage du service..."
ssh "$TARGET" "sudo systemctl restart weatherdress"

echo "==> Déployé avec succès sur $TARGET"

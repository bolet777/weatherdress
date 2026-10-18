#!/usr/bin/env bash
# À exécuter sur le Raspberry Pi
set -e

echo "==> Arrêt des services weatherdress et weatherdress-config..."
sudo systemctl stop weatherdress weatherdress-config || true

echo "==> Désactivation des services..."
sudo systemctl disable weatherdress weatherdress-config || true

echo "==> Suppression des fichiers service..."
sudo rm -f /etc/systemd/system/weatherdress.service /etc/systemd/system/weatherdress-config.service
sudo systemctl daemon-reload

echo "Services weatherdress et weatherdress-config supprimés."

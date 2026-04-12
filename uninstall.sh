#!/usr/bin/env bash
# À exécuter sur le Raspberry Pi
set -e

echo "==> Arrêt du service weatherdress..."
sudo systemctl stop weatherdress || true

echo "==> Désactivation du service..."
sudo systemctl disable weatherdress || true

echo "==> Suppression du fichier service..."
sudo rm -f /etc/systemd/system/weatherdress.service
sudo systemctl daemon-reload

echo "Service weatherdress supprimé."

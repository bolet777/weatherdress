#!/usr/bin/env bash
# À exécuter sur le Raspberry Pi depuis le répertoire weatherdress/
set -e

echo "==> Vérification de Python 3..."
python3 --version

echo "==> Installation des dépendances..."
pip3 install -r requirements.txt

echo "==> Copie du service systemd..."
sudo cp weatherdress.service /etc/systemd/system/weatherdress.service

echo "==> Activation et démarrage du service..."
sudo systemctl daemon-reload
sudo systemctl enable weatherdress
sudo systemctl start weatherdress

echo ""
echo "Service weatherdress démarré."
echo "Vérifier avec : sudo systemctl status weatherdress"

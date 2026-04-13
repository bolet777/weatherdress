#!/usr/bin/env bash
# À exécuter sur le Raspberry Pi depuis le répertoire weatherdress/
set -e

is_raspberry_pi() {
  if [ -f /proc/device-tree/model ]; then
    grep -qi raspberry /proc/device-tree/model 2>/dev/null
    return $?
  fi
  return 1
}

# Détecte PEP 668 (environnement Python géré par le système, ex. Python 3.13+ sur Raspberry Pi OS).
externally_managed_env() {
  python3 -c 'import pathlib, sysconfig; p = pathlib.Path(sysconfig.get_path("stdlib")) / "EXTERNALLY-MANAGED"; import sys; sys.exit(0 if p.is_file() else 1)'
}

echo "==> Vérification de Python 3..."
python3 --version

if is_raspberry_pi; then
  echo "==> Raspberry Pi détecté : pygame et requests via apt (paquets ARM précompilés)."
  export DEBIAN_FRONTEND=noninteractive
  sudo apt-get update -qq
  sudo apt-get install -y --no-install-recommends python3-pygame python3-requests
else
  echo "==> Installation des dépendances (pip)..."
  pip_args=(-r requirements.txt)
  if externally_managed_env; then
    echo "    (PEP 668 : utilisation de --break-system-packages)"
    pip_args=(--break-system-packages "${pip_args[@]}")
  fi
  pip3 install "${pip_args[@]}"
fi

echo "==> Copie du service systemd..."
sudo cp weatherdress.service /etc/systemd/system/weatherdress.service

echo "==> Activation et démarrage du service..."
sudo systemctl daemon-reload
sudo systemctl enable weatherdress
sudo systemctl start weatherdress

echo ""
echo "Service weatherdress démarré."
echo "Vérifier avec : sudo systemctl status weatherdress"

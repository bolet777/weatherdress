#!/usr/bin/env bash
# À exécuter sur le Raspberry Pi depuis le clone (ex. bash scripts/install.sh).
set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$(cd "$SCRIPT_DIR/.." && pwd)"

INSTALL_DIR="$(pwd)"

# Utilisateur du service : WEATHERDRESS_USER, sinon SUDO_USER (ex. sudo depuis weather), sinon propriétaire du répertoire.
if [ -n "${WEATHERDRESS_USER:-}" ]; then
  RUN_USER="$WEATHERDRESS_USER"
elif [ -n "${SUDO_USER:-}" ] && [ "$SUDO_USER" != "root" ]; then
  RUN_USER="$SUDO_USER"
else
  RUN_USER="$(stat -c '%U' .)"
fi

RUN_HOME="$(getent passwd "$RUN_USER" | cut -d: -f6)"
if [ -z "$RUN_HOME" ]; then
  echo "Erreur : utilisateur système « $RUN_USER » introuvable (WEATHERDRESS_USER / SUDO_USER / propriétaire du clone)." >&2
  exit 1
fi

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

echo "==> Génération du service systemd (répertoire : $INSTALL_DIR, utilisateur : $RUN_USER)..."
if [ ! -f packaging/weatherdress.service.in ]; then
  echo "Erreur : packaging/weatherdress.service.in introuvable." >&2
  exit 1
fi
sed \
  -e "s|@INSTALL_DIR@|${INSTALL_DIR}|g" \
  -e "s|@RUN_USER@|${RUN_USER}|g" \
  -e "s|@RUN_HOME@|${RUN_HOME}|g" \
  packaging/weatherdress.service.in | sudo tee /etc/systemd/system/weatherdress.service > /dev/null

echo "==> Activation et démarrage du service..."
sudo systemctl daemon-reload
sudo systemctl enable weatherdress
sudo systemctl start weatherdress

echo ""
echo "Service weatherdress démarré."
echo "Vérifier avec : sudo systemctl status weatherdress"

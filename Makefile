.PHONY: install run deploy test

install:
	pip install -r requirements-dev.txt

run:
	PYTHONPATH=src python3 -m weatherdress.main

deploy:
	@if [ -z "$(HOST)" ]; then \
		echo "Erreur: HOST non défini."; \
		echo "Usage: make deploy HOST=weather@weather.local"; \
		exit 1; \
	fi
	@echo "==> Connexion à $(HOST) (git pull + redémarrage du service)…"
	ssh -tt -o ConnectTimeout=20 "$(HOST)" 'cd ~/weatherdress || { echo "[deploy] Dossier ~/weatherdress introuvable." >&2; exit 1; }; test -f scripts/launch.sh || { echo "[deploy] scripts/launch.sh absent sur le Pi : git pull origin main dans ~/weatherdress (fichier sur main)." >&2; exit 1; }; bash ./scripts/launch.sh'

test:
	pytest tests/

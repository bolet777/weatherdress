.PHONY: install run deploy test

install:
	pip install -r requirements-dev.txt

run:
	python main.py

deploy:
	@if [ -z "$(HOST)" ]; then \
		echo "Erreur: HOST non défini."; \
		echo "Usage: make deploy HOST=weather@weatherdress.local"; \
		exit 1; \
	fi
	ssh "$(HOST)" 'cd ~/weatherdress && ./launch.sh'

test:
	pytest tests/

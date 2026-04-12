.PHONY: install run deploy test

install:
	pip install -r requirements-dev.txt

run:
	python main.py

deploy:
	@if [ -z "$(HOST)" ]; then echo "Usage: make deploy HOST=pi@raspberrypi.local"; exit 1; fi
	./deploy.sh $(HOST)

test:
	pytest tests/

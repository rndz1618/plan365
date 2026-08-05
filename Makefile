.PHONY: run install seed docker-build docker-up docker-down service-install clean

install:
	python3 -m venv .venv
	.venv/bin/pip install -r requirements.txt

run:
	.venv/bin/python -m uvicorn main:app --host 0.0.0.0 --port 8000 --workers 1

seed:
	.venv/bin/python seed_demo.py

docker-build:
	docker compose build

docker-up:
	docker compose up -d

docker-down:
	docker compose down

docker-logs:
	docker compose logs -f plan365

service-install:
	sudo cp deploy/plan365.service /etc/systemd/system/
	sudo systemctl daemon-reload
	sudo systemctl enable --now plan365
	@echo "Open http://$$(hostname -I | awk '{print $$1}'):8000"

clean:
	rm -rf __pycache__ app/__pycache__ app/routers/__pycache__ .venv

.PHONY: install test dev-api dev-web openapi sync-prototype

install:
	pip install -e "apps/api[dev]"
	cd apps/web && npm install

test:
	cd apps/api && python -m pytest -q

dev-api:
	cd apps/api && uvicorn app.main:app --reload --port 8001

dev-web:
	cd apps/web && npm run dev

openapi:
	cd apps/api && python scripts/export_openapi.py

sync-prototype:
	cp index.html apps/web/public/prototype.html

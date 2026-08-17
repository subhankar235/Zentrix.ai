.PHONY: dev backend frontend up down lint format test

dev:
	@echo "Starting development servers..."
	cd apps/backend && uvicorn app.main:app --reload --port 8000 &
	cd apps/frontend && npm run dev &

up:
	docker-compose up -d

down:
	docker-compose down

build:
	docker-compose build

lint:
	cd apps/frontend && npm run lint
	cd apps/backend && python -m ruff check .

format:
	cd apps/frontend && npx prettier --write .
	cd apps/backend && python -m ruff format .

test:
	cd apps/frontend && npm run test
	cd apps/backend && python -m pytest

clean:
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name .pytest_cache -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name node_modules -exec rm -rf {} + 2>/dev/null || true
	rm -rf apps/frontend/.next apps/frontend/out

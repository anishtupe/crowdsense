.PHONY: up down backend frontend test

up:
	docker compose up -d db redis

down:
	docker compose down

backend:
	cd backend && uvicorn app.main:app --reload --port 8000

frontend:
	cd frontend && npm run dev

test:
	cd backend && pytest -q

.PHONY: build up down restart dev dev-frontend dev-backend logs clean

# === Docker (production) ===

# Build all images and start
build:
	docker compose build
	docker compose up -d

# Start (assumes images already built)
up:
	docker compose up -d

# Stop everything
down:
	docker compose down

# Rebuild and restart
restart:
	docker compose down
	docker compose build
	docker compose up -d

# Tail logs
logs:
	docker compose logs -f

logs-backend:
	docker compose logs -f mimir-backend

# === Local development ===

# Install all dependencies
install:
	cd frontend && npm install
	cd backend && pip install -e ".[dev]"

# Start frontend dev server (Vite HMR on :3081, proxies /api to :8000)
dev-frontend:
	cd frontend && npm run dev

# Start backend dev server (uvicorn with reload on :8000)
dev-backend:
	cd backend && python -m uvicorn src.main:app --host 0.0.0.0 --port 8000 --reload

# === Utilities ===

# Run backend tests
test:
	cd backend && python -m pytest -v

# Remove build artifacts and data
clean:
	rm -rf frontend/dist frontend/node_modules/.vite
	docker compose down -v --remove-orphans 2>/dev/null || true

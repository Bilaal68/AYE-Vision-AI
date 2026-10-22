#!/usr/bin/env bash
# ================================================================
# AYE Vision - One-Click Start Script
# ================================================================
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

echo "=================================================="
echo "  Starting AYE Vision Platform..."
echo "=================================================="

# 1. Start containers in background
echo "[1/3] Starting containers (building if needed)..."
docker compose up -d

# 2. Wait for services
echo "[2/3] Waiting for API and database to become ready..."
for i in {1..30}; do
    if docker compose exec -T api python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health')" >/dev/null 2>&1; then
        echo "  API service is healthy!"
        break
    fi
    echo "  Waiting for services to initialize ($i/30)..."
    sleep 3
done

# 3. Run database migrations and seed data
echo "[3/3] Running database migrations & seeding demo data..."
docker compose exec -T api alembic upgrade head
docker compose exec -T api python /app/scripts/seed_data.py || docker compose exec -T api python scripts/seed_data.py || echo "  Notice: Seed data already present or initialized."
docker compose exec -T api python /app/scripts/seed_all.py || true

echo ""
echo "=================================================="
echo "  AYE Vision is now running!"
echo "=================================================="
echo "  Dashboard (Nginx SSL): https://localhost:8443"
echo "  Dashboard (Direct):    http://localhost:3000"
echo "  API Docs (Swagger):    http://localhost:8000/docs"
echo "  MinIO Storage Console: http://localhost:9001"
echo ""
echo "  Default Login Credentials:"
echo "    Email:    admin@visionai.com"
echo "    Password: admin123456"
echo "=================================================="

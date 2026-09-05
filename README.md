# Security Intelligence Platform

Learning project: a situational-awareness foundation (React + Django), not a finished intelligence system.

This repository currently provides **architecture and wiring only**. Camera, vehicle, satellite, identity, and financial features are placeholders.

## What runs today

```
Frontend (Vite / React)
        ↓  GET /api/health/
Django REST API
        ↓
PostgreSQL (PostGIS extension enabled)
Redis (Celery broker; no jobs yet)
```

## Quick start (Docker)

```bash
cp .env.example .env
docker compose up --build
```

- Frontend: http://localhost:5173
- API health: http://localhost:8000/api/health/
- Django admin: http://localhost:8000/admin/

Create an admin user (optional):

```bash
docker compose exec backend python manage.py createsuperuser
```

## Quick start (local processes)

You still need PostgreSQL and Redis. Easiest: start only those with Docker, run apps on the host.

```bash
cp .env.example .env
docker compose up db redis -d

cd backend
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python manage.py migrate
python manage.py runserver 0.0.0.0:8000

cd ../frontend
npm install
npm run dev
```

The Vite dev server proxies `/api` to Django (`localhost:8000`, or `backend:8000` in Compose).

## Documentation

| Topic | File |
| --- | --- |
| Architecture | [docs/architecture/overview.md](docs/architecture/overview.md) |
| Frontend | [docs/architecture/frontend.md](docs/architecture/frontend.md) |
| Backend | [docs/architecture/backend.md](docs/architecture/backend.md) |
| Database | [docs/database/overview.md](docs/database/overview.md) |
| AI layout | [docs/architecture/ai-services.md](docs/architecture/ai-services.md) |
| Data flow | [docs/architecture/data-flow.md](docs/architecture/data-flow.md) |
| Day-to-day workflow | [docs/development/getting-started.md](docs/development/getting-started.md) |

Previous cyber-range / FastAPI ML service code is kept under `docs/archive/` so nothing useful was thrown away. It is **not** part of the running foundation.

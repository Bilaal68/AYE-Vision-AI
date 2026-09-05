# Architecture overview

The platform is a **monorepo**, not a set of microservices.

## Why this shape

The previous prototype mixed cyber-defense ideas (attack simulation, FastAPI anomaly service, graph database language) with empty Django apps. The new goal is a situational-awareness product (maps, cameras, investigations). For a learning project that means:

- One HTTP API: Django + Django REST Framework
- One UI: React (Vite)
- One database: PostgreSQL, with PostGIS installed for later map queries
- Redis + Celery **configured**, with **zero tasks** until a feature needs a background job
- Computer vision code in `ai/`, called later through `backend/services/` — not a second web server

## Runtime (foundation)

```
┌─────────────┐     GET /api/health/      ┌─────────────┐
│   React     │ ─────────────────────────▶│   Django    │
│   Vite      │                           │   DRF       │
└─────────────┘                           └──────┬──────┘
                                                 │
                                          ┌──────▼──────┐
                                          │ PostgreSQL  │
                                          │ + PostGIS   │
                                          └─────────────┘
                                                 │
                                          ┌──────▼──────┐
                                          │    Redis    │
                                          │ (Celery)    │
                                          └─────────────┘
```

## Future AI (not built)

```
ai/ packages (OpenCV, later models)
        ↓  imported by
backend/services/*  (thin adapters)
        ↓  used by
Django apps (cameras, identity, vehicles, …)
        ↓  stored in
PostgreSQL
        ↓  shown in
React
```

There is no live FastAPI sidecar in this foundation. The old FastAPI service is archived.

## Domain split

Django apps are folders for **future** features. Most contain no models yet. That is deliberate: you add a model when you implement that feature, not before.

| App | Purpose now | Later |
| --- | --- | --- |
| `users` | Custom user + role | Login UI, tokens |
| `system_monitoring` | Health endpoint | Metrics |
| `investigations`, `cameras`, `vehicles`, `satellite`, `incidents`, `alerts`, `identity`, `financial`, `intelligence` | Empty URL routes | Prototype 1+ |

## Security (foundation only)

- Secrets from environment variables (`.env` is gitignored)
- CORS allow-list for the Vite origin
- DRF default permission: authenticated
- Health check is public (`AllowAny`)
- Role field on `User`: `admin`, `analyst`, `viewer`
- Permission classes in `backend/common/permissions/`
- Audit **logging** middleware (log lines, not a full audit table yet)
- Production settings refuse an insecure `SECRET_KEY`

## What is intentionally missing

Real CCTV, face matching, government identity, banks, satellites, license-plate tracking, and correlation engines. Those belong in later prototypes, using mock data first.

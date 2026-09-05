# Data flow

## Foundation (what you can run today)

```
Browser
  → Vite (port 5173)
      → proxy /api/* 
          → Django (port 8000)
              → PostgreSQL (health check: connection.ensure_connection)
```

The dashboard displays the JSON from `GET /api/health/`.

## Intended flow for later prototypes (not implemented)

```
Sensor / mock file / operator upload
  → Django API
      → domain app (cameras, vehicles, …)
          → optional Celery task
              → backend/services/* 
                  → ai/* 
          → PostgreSQL (+ PostGIS for coordinates)
  → React Query refetch
      → map / timeline / alert UI
```

## Future AI diagram

```
Future AI package
      ↓
Django API
      ↓
Database
      ↓
Frontend
```

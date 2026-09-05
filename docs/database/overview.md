# Database architecture

## Engine

PostgreSQL 16 via the official PostGIS image (`postgis/postgis:16-3.4`).

`infrastructure/postgres/init.sql` runs **once** on an empty volume:

- `CREATE EXTENSION postgis;`
- `CREATE EXTENSION vector;` (optional, unused now)

## Django connection

`django.db.backends.postgresql` (not GeoDjango yet).

**Decision:** GeoDjango needs GDAL on every machine that runs `manage.py`. That is painful for learning. The database already has PostGIS. When a model needs a `PointField`, switch:

1. Install GDAL in `backend/Dockerfile`
2. Add `django.contrib.gis` to `INSTALLED_APPS`
3. Set `DB_ENGINE=django.contrib.gis.db.backends.postgis`

Until then, store coordinates as decimal fields or wait for that switch.

## Models in the foundation

Only `users.User` (custom user + `role`).

Planned later (do not create until the feature needs them): Person, Vehicle, Camera, Investigation, Alert, SatelliteImage, Incident, Evidence, TimelineEvent.

## Migrations

```bash
cd backend
python manage.py makemigrations
python manage.py migrate
```

If you already ran the old empty project against the same Docker volume, you may need `docker compose down -v` once to start from a clean database (this destroys local data).

# Development workflow

## Everyday loop

1. Change one feature at a time (one Django app, one frontend page).
2. Keep models out of apps you are not building yet.
3. Use mock JSON in `data/mock/` until a real serializer exists.
4. Check `GET /api/health/` if the UI cannot reach the API.

## Useful commands

```bash
# API
cd backend
python manage.py runserver
python manage.py check
python manage.py migrate

# UI
cd frontend
npm run dev
npm run build   # TypeScript + Vite production build

# Stack
docker compose up --build
docker compose logs -f backend
```

## Celery (later)

```bash
cd backend
celery -A config worker -l info
```

There are no tasks to consume yet.

## Nginx

`infrastructure/nginx/nginx.conf` is ready for a reverse proxy. Compose does not start Nginx so you can use Vite hot reload during learning.

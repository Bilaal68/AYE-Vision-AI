# Backend structure

Stack: Django, Django REST Framework, PostgreSQL, Redis, Celery (configured only).

## Folders

| Path | Why it exists |
| --- | --- |
| `config/` | Project package: settings, URLs, WSGI/ASGI, Celery app |
| `config/settings/` | `base.py` shared, `development.py` local, `production.py` strict |
| `apps/` | One Django app per domain |
| `common/` | Permissions, pagination, exception shape, audit middleware |
| `services/` | Adapters that will call `ai/` packages. No algorithms yet. |
| `tests/` | Project-level tests |

## App file pattern (use when a feature starts)

```
models.py
serializers.py
views.py
urls.py
services.py   # app-local orchestration, optional
permissions.py
tests.py
```

The foundation only adds extra files where they are needed (`users`, `system_monitoring`). Empty apps have `models.py` + `urls.py` so you know where to start.

## Settings module

`DJANGO_SETTINGS_MODULE=config.settings.development`

`manage.py`, `wsgi.py`, and `asgi.py` default to development.

## Auth

`AUTH_USER_MODEL = users.User` with a `role` field. Token authentication is enabled (`rest_framework.authtoken`) so Prototype 1 can add token login without new packages. Session auth still works for `/admin/`.

## Celery

`config/celery.py` reads `CELERY_*` from Django settings. Do not start a worker until you have a real task. Redis is running so the broker exists.

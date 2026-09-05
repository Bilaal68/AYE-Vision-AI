"""Celery application.

No background tasks are registered yet. This file exists so Prototype 1
can add tasks in Django apps without changing project wiring.
"""

import os

from celery import Celery

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.development")

app = Celery("secint")
app.config_from_object("django.conf:settings", namespace="CELERY")
app.autodiscover_tasks()

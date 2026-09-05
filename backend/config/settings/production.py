"""Production settings.

Used later behind Nginx. Do not use DEBUG=True here.
"""

import os

from .base import *  # noqa: F403

DEBUG = False

secret = os.environ.get("SECRET_KEY", "")
if not secret or secret.startswith("django-insecure"):
    raise ValueError("Set a real SECRET_KEY environment variable for production.")
SECRET_KEY = secret

ALLOWED_HOSTS = [
    host.strip()
    for host in os.environ.get("ALLOWED_HOSTS", "").split(",")
    if host.strip()
]
if not ALLOWED_HOSTS:
    raise ValueError("Set ALLOWED_HOSTS for production.")

SECURE_BROWSER_XSS_FILTER = True
SECURE_CONTENT_TYPE_NOSNIFF = True
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
X_FRAME_OPTIONS = "DENY"

import os

from .base import *  # noqa: F403

DEBUG = os.environ.get("DEBUG", "True") == "True"

# Local learning setup: allow the Vite dev server and Django itself.
ALLOWED_HOSTS = list(
    {
        *ALLOWED_HOSTS,  # noqa: F405
        "localhost",
        "127.0.0.1",
        "backend",
        "0.0.0.0",
    }
)

# Never use this in production. Production settings refuse an insecure SECRET_KEY.

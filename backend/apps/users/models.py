"""Custom user with a simple role field (RBAC foundation)."""

from django.contrib.auth.models import AbstractUser
from django.db import models


class User(AbstractUser):
    class Roles(models.TextChoices):
        ADMIN = "admin", "Admin"
        ANALYST = "analyst", "Analyst"
        VIEWER = "viewer", "Viewer"

    role = models.CharField(
        max_length=32,
        choices=Roles.choices,
        default=Roles.VIEWER,
        help_text="Application role used by DRF permission classes.",
    )

    def __str__(self):
        return f"{self.username} ({self.role})"

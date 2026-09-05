from django.contrib import admin
from django.urls import include, path

from apps.system_monitoring.views import HealthCheckView

urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/health/", HealthCheckView.as_view(), name="health-check"),
    path("api/auth/", include("apps.users.urls")),
    path("api/investigations/", include("apps.investigations.urls")),
    path("api/cameras/", include("apps.cameras.urls")),
    path("api/vehicles/", include("apps.vehicles.urls")),
    path("api/satellite/", include("apps.satellite.urls")),
    path("api/incidents/", include("apps.incidents.urls")),
    path("api/alerts/", include("apps.alerts.urls")),
    path("api/identity/", include("apps.identity.urls")),
    path("api/financial/", include("apps.financial.urls")),
    path("api/intelligence/", include("apps.intelligence.urls")),
    path("api/system/", include("apps.system_monitoring.urls")),
]

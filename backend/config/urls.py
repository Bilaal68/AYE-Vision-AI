from django.contrib import admin
from django.urls import path, include
from django.http import JsonResponse

def health_check(request):
    return JsonResponse({"status": "ok", "service": "backend"})

urlpatterns = [
    path('admin/', admin.site.urls),
    path('api/health/', health_check, name='health_check'),
    path('api/events/', include('apps.events.urls')),
    path('api/incidents/', include('apps.incidents.urls')),
    path('api/entities/', include('apps.entities.urls')),
    path('api/graph/', include('apps.graph.urls')),
    path('api/investigations/', include('apps.investigations.urls')),
    path('api/accounts/', include('apps.accounts.urls')),
    path('api/audit/', include('apps.audit.urls')),
]

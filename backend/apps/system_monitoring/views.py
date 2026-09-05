from django.db import connection
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView


class HealthCheckView(APIView):
    """Public liveness/readiness probe used by the frontend and Docker."""

    authentication_classes = []
    permission_classes = [AllowAny]

    def get(self, request):
        database = "ok"
        try:
            connection.ensure_connection()
        except Exception:
            database = "error"

        status = "ok" if database == "ok" else "degraded"
        http_status = 200 if database == "ok" else 503
        return Response(
            {
                "status": status,
                "service": "backend",
                "database": database,
            },
            status=http_status,
        )

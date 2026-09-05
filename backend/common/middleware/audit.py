import logging

from django.utils.deprecation import MiddlewareMixin

logger = logging.getLogger("secint.audit")

SKIP_PREFIXES = ("/static/", "/admin/jsi18n/", "/api/health/")


class AuditLogMiddleware(MiddlewareMixin):
    """Foundation for request audit logging.

    Writes a structured log line. Persisting rows to the database is deferred
    until Prototype 1 so the foundation stays small and does not create noise
    during health checks.
    """

    def process_response(self, request, response):
        path = request.path
        if path.startswith(SKIP_PREFIXES):
            return response

        user = getattr(request, "user", None)
        username = getattr(user, "username", None) if user else None
        logger.info(
            "audit method=%s path=%s status=%s user=%s",
            request.method,
            path,
            response.status_code,
            username or "anonymous",
        )
        return response

from rest_framework.views import exception_handler


def custom_exception_handler(exc, context):
    """Wrap DRF errors in a stable JSON shape for the frontend."""
    response = exception_handler(exc, context)
    if response is None:
        return None

    detail = response.data
    response.data = {
        "error": True,
        "status_code": response.status_code,
        "detail": detail,
    }
    return response

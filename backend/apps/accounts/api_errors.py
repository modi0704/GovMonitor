"""DRF exception handler: 401 (not 403) for missing sign-in, with a stable ``code`` field."""

from rest_framework import exceptions, status
from rest_framework.views import exception_handler as drf_exception_handler


def exception_handler(exc, context):
    response = drf_exception_handler(exc, context)
    if response is None:
        return None
    request = context.get("request")
    if isinstance(exc, exceptions.NotAuthenticated | exceptions.AuthenticationFailed):
        expired = bool(getattr(getattr(request, "_request", None), "session_expired", False))
        response.status_code = status.HTTP_401_UNAUTHORIZED
        response.data = {
            "detail": "Your session has ended. Please sign in again." if expired else "Please sign in.",
            "code": "session_expired" if expired else "not_authenticated",
        }
    elif isinstance(response.data, dict) and "detail" in response.data and "code" not in response.data:
        code = getattr(exc, "default_code", None)
        if isinstance(getattr(exc, "detail", None), exceptions.ErrorDetail):
            code = exc.detail.code
        if code:
            response.data["code"] = code
    return response

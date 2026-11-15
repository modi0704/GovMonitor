"""Captures request id, IP and user agent for audit rows (P3.2). Placed first in MIDDLEWARE."""

import re
import uuid

from apps.audit import services

_SAFE_ID = re.compile(r"^[A-Za-z0-9._-]{8,64}$")


class AuditContextMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        incoming = request.META.get("HTTP_X_REQUEST_ID", "")
        request.request_id = incoming if _SAFE_ID.match(incoming) else uuid.uuid4().hex
        request.audit_rows = 0
        token = services.set_request(request)
        try:
            response = self.get_response(request)
        finally:
            services.reset_request(token)
        response["X-Request-ID"] = request.request_id
        return response

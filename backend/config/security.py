"""Security headers for every response (P13.1).

The content security policy allows nothing outside this site: the app ships every script, style,
font and image itself (no CDN, no hosted fonts — MASTERPLAN 0.2). ``style-src 'unsafe-inline'``
is needed for the style attributes React and the chart library set; scripts stay strict.
"""

from django.conf import settings

CSP = "; ".join(
    [
        "default-src 'self'",
        "script-src 'self'",
        "style-src 'self' 'unsafe-inline'",
        "img-src 'self' data: blob:",
        "font-src 'self'",
        "connect-src 'self'",
        "object-src 'none'",
        "frame-ancestors 'none'",
        "base-uri 'self'",
        "form-action 'self'",
    ]
)
# Camera only for this site (phone MOV photos); nothing else.
PERMISSIONS = "camera=(self), microphone=(), geolocation=(), payment=(), usb=()"


class SecurityHeadersMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        response.headers.setdefault(
            "Content-Security-Policy", getattr(settings, "CONTENT_SECURITY_POLICY", CSP)
        )
        response.headers.setdefault("Permissions-Policy", PERMISSIONS)
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("Cross-Origin-Opener-Policy", "same-origin")
        return response

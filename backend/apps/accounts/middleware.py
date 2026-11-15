"""Idle sign-out (P1.4): a session unused for SESSION_IDLE_MINUTES is ended."""

from django.contrib.auth import logout

from apps.accounts import services


class SessionIdleMiddleware:
    """Placed after AuthenticationMiddleware."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        request.session_expired = False
        user = getattr(request, "user", None)
        if user is not None and user.is_authenticated:
            if services.is_session_idle(request):
                logout(request)
                request.session_expired = True
            else:
                services.touch_session(request)
        return self.get_response(request)

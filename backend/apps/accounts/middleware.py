"""Idle sign-out (P1.4): a session unused for SESSION_IDLE_MINUTES is ended.

Only real API use counts as activity: background polls (``X-Background: 1``, e.g. the notification
bell) and page loads do not refresh the timer, so an open but unattended tab still signs out. Page
loads therefore never write the session, which also avoids a race with a concurrent sign-out
(Django's SessionInterrupted).
"""

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
            elif counts_as_activity(request):
                services.touch_session(request)
        return self.get_response(request)


def counts_as_activity(request) -> bool:
    path = request.path
    if not (path.startswith("/api/") or path.startswith("/platform/api/")):
        return False
    return request.headers.get("X-Background") != "1"

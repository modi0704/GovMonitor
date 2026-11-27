"""Idle sign-out (P1.4): a session unused for SESSION_IDLE_MINUTES is ended.

Only real API use counts as activity: background polls (``X-Background: 1``, e.g. the notification
bell) and page loads do not refresh the timer, so an open but unattended tab still signs out. Page
loads therefore never write the session, which also avoids a race with a concurrent sign-out
(Django's SessionInterrupted).
"""

from django.conf import settings
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


class NoLoginMiddleware:
    """Testing mode (``LOGIN_DISABLED``): a request with nobody signed in acts as an agency
    administrator, so the app opens without a sign-in page. Nothing is written to the session (no
    sign-in record per request); the agency context is set exactly as a sign-in would. The platform
    area keeps its own sign-in. Placed after SessionIdleMiddleware."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if (
            settings.LOGIN_DISABLED
            and not request.path.startswith("/platform/")
            and not getattr(request, "user", None).is_authenticated
        ):
            user = default_user()
            if user is not None:
                request.user = user
                request._cached_user = user
                request.agency_id = user.agency_id
        return self.get_response(request)


def default_user():
    """``LOGIN_AS`` if it names an active account, else the first active top-office administrator of
    the first active agency. Read as the owner role (no agency is chosen yet), then reloaded inside
    that agency's context like a normal sign-in."""
    from apps.accounts.models import RoleAssignment, User
    from apps.tenancy import context
    from apps.tenancy.models import Agency

    active = Agency.objects.using("owner").filter(status="active").values_list("id", flat=True)
    candidates = User.objects.using("owner").filter(is_active=True, agency_id__in=list(active))
    chosen = None
    if settings.LOGIN_AS:
        chosen = candidates.filter(email=settings.LOGIN_AS).first()
    if chosen is None:
        admin = (
            RoleAssignment.objects.using("owner")
            .filter(level="admin", office__parent__isnull=True, user__in=candidates)
            .order_by("agency__created_at", "user__created_at")
            .select_related("user")
            .first()
        )
        chosen = admin.user if admin else None
    if chosen is None:
        return None
    context.set_agency(chosen.agency_id)
    return User.objects.filter(pk=chosen.pk).first()

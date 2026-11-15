"""Per-request agency context (MASTERPLAN 6.1, P1.3).

Placed after SessionMiddleware and before AuthenticationMiddleware. It opens one transaction for the
whole request and runs ``SET LOCAL app.agency_id`` taken from the signed-in user's session, so that
row-level security applies even to the user lookup done by AuthenticationMiddleware. (Django's
ATOMIC_REQUESTS only wraps the view, which would be too late for that lookup; the view's atomic
block becomes a savepoint inside this transaction.)

A session's agency is written at sign-in (``SESSION_AGENCY_KEY``) and cannot be chosen by the
client: Django sessions are stored server-side. If the stored user does not belong to that agency,
RLS hides the user row and the request is anonymous.
"""

from django.db import transaction

from apps.tenancy import context

SESSION_AGENCY_KEY = "_agency_id"


class TenantMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        agency_id = None
        session = getattr(request, "session", None)
        if session is not None:
            agency_id = session.get(SESSION_AGENCY_KEY)
        with transaction.atomic(using="default"):
            context.set_agency(agency_id)
            request.agency_id = context.current_agency_id()
            try:
                response = self.get_response(request)
                if response.status_code >= 500:
                    transaction.set_rollback(True, using="default")
            finally:
                context.clear()
        return response

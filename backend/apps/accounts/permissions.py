"""Permissions (MASTERPLAN 6.6). Office-scope functions are added in P1.8."""

from rest_framework.permissions import BasePermission

from apps.tenancy.models import Agency


class IsSignedIn(BasePermission):
    """Default for every API view: signed in, agency active, no pending forced password change.

    Views that must stay reachable while a password change is pending (``me``, sign-out, change
    password) set ``allow_pending_password_change = True``.
    """

    message = "Please sign in."

    def has_permission(self, request, view):
        user = request.user
        if not (user and user.is_authenticated):
            return False
        if not hasattr(request, "_agency_status"):
            request._agency_status = (
                Agency.objects.filter(pk=user.agency_id).values_list("status", flat=True).first()
            )
        if request._agency_status != Agency.Status.ACTIVE:
            self.message = "Your agency's access is suspended."
            return False
        if user.must_change_password and not getattr(view, "allow_pending_password_change", False):
            self.message = "You must change your password before continuing."
            return False
        return True

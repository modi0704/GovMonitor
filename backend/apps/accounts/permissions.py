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


# ---- Office scope (MASTERPLAN 6.6) -------------------------------------------------------------
# An assignment at an office covers that office and every office beneath it. Offices carry a
# materialised path (/root/…/self/), so "beneath" is a prefix test on that path.


def _assignments(user) -> list[tuple[str, str, bool]]:
    """(office path, level, office is root) for every assignment of ``user``; cached per object."""
    cached = getattr(user, "_gm_assignments", None)
    if cached is None:
        from apps.accounts.models import RoleAssignment

        cached = [
            (path, level, parent_id is None)
            for path, level, parent_id in RoleAssignment.objects.filter(user_id=user.pk).values_list(
                "office__path", "level", "office__parent_id"
            )
        ]
        user._gm_assignments = cached
    return cached


def forget_cached_scope(user) -> None:
    if hasattr(user, "_gm_assignments"):
        del user._gm_assignments


def _scope_q(user, admin_only: bool):
    from django.db.models import Q

    q = Q(pk__in=[])
    for path, level, _ in _assignments(user):
        if admin_only and level != "admin":
            continue
        q |= Q(path__startswith=path)
    return q


def scope(user):
    """Queryset of offices the user may view: beneath any office they are assigned to."""
    from apps.structure.models import Office

    if not (user and user.is_authenticated):
        return Office.objects.none()
    return Office.objects.filter(_scope_q(user, admin_only=False))


def edit_scope(user):
    """Queryset of offices the user may change: beneath any office they are an ``admin`` of."""
    from apps.structure.models import Office

    if not (user and user.is_authenticated):
        return Office.objects.none()
    return Office.objects.filter(_scope_q(user, admin_only=True))


def _office_path(office) -> str:
    if isinstance(office, str):
        return office
    return office.path


def can_view(user, office) -> bool:
    if not (user and user.is_authenticated):
        return False
    path = _office_path(office)
    return any(path.startswith(p) for p, _, _ in _assignments(user))


def can_edit(user, office) -> bool:
    if not (user and user.is_authenticated):
        return False
    path = _office_path(office)
    return any(level == "admin" and path.startswith(p) for p, level, _ in _assignments(user))


def is_agency_admin(user) -> bool:
    """An ``admin`` assignment at the agency's root office (D1)."""
    if not (user and user.is_authenticated):
        return False
    return any(level == "admin" and is_root for _, level, is_root in _assignments(user))


# ---- DRF permission classes --------------------------------------------------------------------

SAFE_METHODS = ("GET", "HEAD", "OPTIONS")


class IsAgencyAdmin(IsSignedIn):
    """Structure, users, fiscal years, scoring settings, approvals, locking, audit log (6.6)."""

    def has_permission(self, request, view):
        if not super().has_permission(request, view):
            return False
        self.message = "Only the agency administrator can do this."
        return is_agency_admin(request.user)


class ReadOrAgencyAdmin(IsSignedIn):
    """Anyone signed in may read; only the agency administrator may change."""

    def has_permission(self, request, view):
        if not super().has_permission(request, view):
            return False
        if request.method in SAFE_METHODS:
            return True
        self.message = "Only the agency administrator can do this."
        return is_agency_admin(request.user)


class OfficeScoped(IsSignedIn):
    """Object-level check for office-bound objects.

    The view's object must expose an office (``obj.office`` or the object itself being an office,
    or ``view.get_permission_office(obj)``). Reads need ``can_view``; writes need ``can_edit``.
    Out-of-scope objects should already be filtered out of the queryset (so they 404); this is the
    second line of defence.
    """

    def has_object_permission(self, request, view, obj):
        getter = getattr(view, "get_permission_office", None)
        office = getter(obj) if getter else getattr(obj, "office", obj)
        if request.method in SAFE_METHODS:
            return can_view(request.user, office)
        self.message = "You have read-only access to this office."
        return can_edit(request.user, office)


def get_office_or_404(user, office_id, *, edit: bool = False):
    """Fetch an office the user may view (or edit); otherwise 404 — never reveal existence."""
    from django.core.exceptions import ValidationError
    from django.http import Http404

    from apps.structure.models import Office

    qs = edit_scope(user) if edit else scope(user)
    try:
        return qs.get(pk=office_id)
    except (Office.DoesNotExist, ValidationError, ValueError, TypeError) as exc:
        raise Http404("No such office.") from exc


def filter_by_scope(queryset, user, *, office_field: str = "office", edit: bool = False):
    """Base-queryset filter for every office-bound endpoint (P2.6).

    ``office_field`` is the lookup path from the queryset's model to its office (e.g. ``"office"``
    or ``"plan__office"``). Rows outside the user's scope disappear, so their ids answer 404.
    """
    from django.db.models import Q

    q = Q(pk__in=[])
    for path, level, _ in _assignments(user) if (user and user.is_authenticated) else []:
        if edit and level != "admin":
            continue
        q |= Q(**{f"{office_field}__path__startswith": path})
    return queryset.filter(q)


class OfficeScopedQuerysetMixin:
    """For DRF views over office-bound models: ``get_queryset`` is always scoped (P2.6).

    Set ``office_field`` and implement ``base_queryset()``. Unsafe methods use the edit scope.
    """

    office_field = "office"

    def base_queryset(self):  # pragma: no cover - abstract
        raise NotImplementedError

    def get_queryset(self):
        request = self.request
        edit = request.method not in SAFE_METHODS
        return filter_by_scope(self.base_queryset(), request.user, office_field=self.office_field, edit=edit)

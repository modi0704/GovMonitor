"""Users and role assignments, agency administrator only (MASTERPLAN 13: users, role-assignments; P2.5).

Guard rail: the agency always keeps at least one active user with an ``admin`` assignment at the
root office, so it can never lock itself out.
"""

from django.db import IntegrityError, transaction
from django.http import Http404
from rest_framework import serializers, status
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts import permissions as perm
from apps.accounts import services
from apps.accounts.models import RoleAssignment, User
from apps.accounts.permissions import IsAgencyAdmin
from apps.structure.models import Office


def _error(code, message, http=status.HTTP_400_BAD_REQUEST):
    return Response({"detail": message, "code": code}, status=http)


def assignment_payload(ra: RoleAssignment) -> dict:
    return {
        "id": str(ra.id),
        "office": {"id": str(ra.office_id), "code": ra.office.code, "name": ra.office.name},
        "level": ra.level,
        "is_root": ra.office.parent_id is None,
    }


def user_payload(user: User, assignments: list[RoleAssignment] | None = None) -> dict:
    if assignments is None:
        assignments = list(user.role_assignments.select_related("office").order_by("office__path"))
    return {
        "id": str(user.id),
        "email": user.email,
        "full_name": user.full_name,
        "is_active": user.is_active,
        "has_2fa": user.has_2fa,
        "must_change_password": user.must_change_password,
        "locked": bool(user.locked_until),
        "last_login_at": user.last_login.isoformat() if user.last_login else None,
        "created_at": user.created_at.isoformat(),
        "assignments": [assignment_payload(a) for a in assignments],
        "is_agency_admin": any(a.level == "admin" and a.office.parent_id is None for a in assignments),
    }


def _get_user(user_id) -> User:
    user = User.objects.filter(pk=user_id).first()
    if user is None:
        raise Http404()
    return user


def _active_agency_admins_excluding(user_id=None, assignment_id=None) -> int:
    qs = RoleAssignment.objects.filter(level="admin", office__parent__isnull=True, user__is_active=True)
    if user_id:
        qs = qs.exclude(user_id=user_id)
    if assignment_id:
        qs = qs.exclude(pk=assignment_id)
    return qs.values("user_id").distinct().count()


class AssignmentInput(serializers.Serializer):
    office_id = serializers.UUIDField()
    level = serializers.ChoiceField(choices=RoleAssignment.Level.choices)


class UserCreateSerializer(serializers.Serializer):
    email = serializers.EmailField()
    full_name = serializers.CharField(max_length=200, allow_blank=True, default="")
    assignments = AssignmentInput(many=True, required=False, default=list)


def _office(office_id) -> Office:
    office = Office.objects.filter(pk=office_id).first()
    if office is None:
        raise serializers.ValidationError({"office_id": ["No such office."]})
    return office


class UserListView(APIView):
    permission_classes = [IsAgencyAdmin]

    def get(self, request):
        users = list(User.objects.order_by("full_name", "email"))
        by_user: dict = {}
        for ra in RoleAssignment.objects.select_related("office").order_by("office__path"):
            by_user.setdefault(ra.user_id, []).append(ra)
        return Response([user_payload(u, by_user.get(u.id, [])) for u in users])

    @transaction.atomic
    def post(self, request):
        s = UserCreateSerializer(data=request.data)
        s.is_valid(raise_exception=True)
        d = s.validated_data
        temporary = services.generate_temporary_password()
        try:
            with transaction.atomic():
                user = User.objects.create_user(d["email"], temporary, full_name=d["full_name"])
        except IntegrityError:
            return Response({"email": ["A user with this email already exists."]}, status=400)
        for a in d["assignments"]:
            RoleAssignment.objects.create(
                user=user, office=_office(a["office_id"]), level=a["level"], created_by=request.user
            )
        return Response(
            {**user_payload(user), "temporary_password": temporary}, status=status.HTTP_201_CREATED
        )


class UserDetailView(APIView):
    permission_classes = [IsAgencyAdmin]

    def get(self, request, user_id):
        return Response(user_payload(_get_user(user_id)))

    def patch(self, request, user_id):
        user = _get_user(user_id)
        fields = []
        if "full_name" in request.data:
            user.full_name = str(request.data["full_name"])[:200]
            fields.append("full_name")
        if "is_active" in request.data:
            active = bool(request.data["is_active"])
            if not active and user.pk == request.user.pk:
                return _error("self", "You cannot deactivate your own account.")
            if not active and _active_agency_admins_excluding(user_id=user.pk) == 0:
                return _error("last_admin", "The agency must keep at least one active administrator.")
            user.is_active = active
            fields.append("is_active")
        if fields:
            user.save(update_fields=fields)
        return Response(user_payload(user))


class UserResetPasswordView(APIView):
    """The agency administrator resets a password (P1.4): one-time temporary password, shown once."""

    permission_classes = [IsAgencyAdmin]

    def post(self, request, user_id):
        user = _get_user(user_id)
        temporary = services.admin_reset_password(user)
        return Response({"temporary_password": temporary, "user": user_payload(user)})


class UserScopeView(APIView):
    """The offices a user can see and change, as the permission rules compute it."""

    permission_classes = [IsAgencyAdmin]

    def get(self, request, user_id):
        user = _get_user(user_id)
        editable = set(perm.edit_scope(user).values_list("id", flat=True))
        offices = perm.scope(user).order_by("path")
        return Response(
            [
                {
                    "id": str(o.id),
                    "code": o.code,
                    "name": o.name,
                    "depth": o.depth,
                    "can_edit": o.id in editable,
                }
                for o in offices
            ]
        )


class RoleAssignmentCreateSerializer(AssignmentInput):
    user_id = serializers.UUIDField()


class RoleAssignmentListView(APIView):
    permission_classes = [IsAgencyAdmin]

    def post(self, request):
        s = RoleAssignmentCreateSerializer(data=request.data)
        s.is_valid(raise_exception=True)
        d = s.validated_data
        user = _get_user(d["user_id"])
        office = _office(d["office_id"])
        ra, created = RoleAssignment.objects.get_or_create(
            user=user, office=office, defaults={"level": d["level"], "created_by": request.user}
        )
        if not created and ra.level != d["level"]:
            return _change_level(request, ra, d["level"])
        return Response(assignment_payload(ra), status=status.HTTP_201_CREATED if created else 200)


def _removes_last_admin(ra: RoleAssignment) -> bool:
    """True when taking away this root ``admin`` assignment would leave no agency administrator."""
    is_root_admin = ra.level == "admin" and ra.office.parent_id is None
    return is_root_admin and _active_agency_admins_excluding(assignment_id=ra.pk) == 0


LAST_ADMIN = "The agency must keep at least one active administrator."


def _change_level(request, ra: RoleAssignment, level: str) -> Response:
    if level != "admin" and _removes_last_admin(ra):
        return _error("last_admin", LAST_ADMIN)
    ra.level = level
    ra.save(update_fields=["level"])
    return Response(assignment_payload(ra))


class RoleAssignmentDetailView(APIView):
    permission_classes = [IsAgencyAdmin]

    def _get(self, assignment_id) -> RoleAssignment:
        ra = RoleAssignment.objects.select_related("office").filter(pk=assignment_id).first()
        if ra is None:
            raise Http404()
        return ra

    def patch(self, request, assignment_id):
        level = request.data.get("level")
        if level not in RoleAssignment.Level.values:
            return Response({"level": ["Choose admin or read_only."]}, status=400)
        return _change_level(request, self._get(assignment_id), level)

    def delete(self, request, assignment_id):
        ra = self._get(assignment_id)
        if _removes_last_admin(ra):
            return _error("last_admin", LAST_ADMIN)
        ra.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)

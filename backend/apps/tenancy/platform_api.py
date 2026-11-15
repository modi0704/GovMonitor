"""Platform-owner API under /platform/api/ (P1.6, P1.7).

Separate sign-in and separate session (cookie ``gm_platform``) from agency users. All data access
goes through the ``owner`` connection. The whole area answers 404 when DEPLOYMENT_MODE=single.
Without an unexpired support grant, nothing here returns an agency's own data (users, offices,
plans…): only the agency record itself (name, code, status) needed to manage the subscription.
"""

from datetime import timedelta

from django.conf import settings
from django.contrib.auth.hashers import check_password, make_password
from django.contrib.sessions.backends.db import SessionStore
from django.db import transaction
from django.http import Http404
from django.utils import timezone
from rest_framework import exceptions, serializers, status
from rest_framework.authentication import BaseAuthentication, SessionAuthentication
from rest_framework.permissions import AllowAny, BasePermission
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts import twofactor
from apps.accounts.models import RoleAssignment, User
from apps.audit import services as audit
from apps.structure.models import Office
from apps.tenancy import services
from apps.tenancy.models import Agency, PlatformAdmin

COOKIE = "gm_platform"
SESSION_ADMIN_KEY = "platform_admin_id"
SESSION_ACTIVITY_KEY = "last_activity"
OWNER = services.OWNER
_DUMMY_HASH = make_password("platform-timing-equaliser")


class PlatformSessionAuthentication(BaseAuthentication):
    def authenticate(self, request):
        key = request.COOKIES.get(COOKIE)
        if not key:
            return None
        store = SessionStore(session_key=key)
        admin_id = store.get(SESSION_ADMIN_KEY)
        if not admin_id:
            return None
        last = store.get(SESSION_ACTIVITY_KEY, 0)
        if timezone.now().timestamp() - last > settings.SESSION_IDLE_MINUTES * 60:
            store.flush()
            raise exceptions.NotAuthenticated("Your session has ended.")
        admin = PlatformAdmin.objects.using(OWNER).filter(pk=admin_id, is_active=True).first()
        if admin is None:
            return None
        store[SESSION_ACTIVITY_KEY] = int(timezone.now().timestamp())
        store.save()
        request._request.platform_session = store
        request._request.audit_platform_admin = admin
        SessionAuthentication().enforce_csrf(request)  # unsafe methods need the CSRF header
        return (admin, None)

    def authenticate_header(self, request):
        return "Session"


class IsPlatformAdmin(BasePermission):
    def has_permission(self, request, view):
        return isinstance(request.user, PlatformAdmin)


class PlatformView(APIView):
    authentication_classes = [PlatformSessionAuthentication]
    permission_classes = [IsPlatformAdmin]

    def initial(self, request, *args, **kwargs):
        if settings.DEPLOYMENT_MODE != "multi":
            raise Http404()
        super().initial(request, *args, **kwargs)


def _error(code, message, http=status.HTTP_400_BAD_REQUEST):
    return Response({"detail": message, "code": code}, status=http)


def agency_payload(agency: Agency) -> dict:
    return {
        "id": str(agency.id),
        "name": agency.name,
        "code": agency.code,
        "status": agency.status,
        "fiscal_year_start_month": agency.fiscal_year_start_month,
        "timezone": agency.timezone,
        "created_at": agency.created_at.isoformat(),
    }


def _get_agency(agency_id) -> Agency:
    try:
        return Agency.objects.using(OWNER).get(pk=agency_id)
    except (Agency.DoesNotExist, ValueError, Exception) as exc:  # noqa: BLE001 — bad id = 404
        raise Http404() from exc


class PlatformLoginView(PlatformView):
    authentication_classes: list = []
    permission_classes = [AllowAny]

    def post(self, request):
        SessionAuthentication().enforce_csrf(request)
        email = str(request.data.get("email", "")).strip().lower()
        password = str(request.data.get("password", ""))
        code = str(request.data.get("code", ""))
        with transaction.atomic(using=OWNER):
            admin = PlatformAdmin.objects.using(OWNER).select_for_update().filter(email=email).first()
            if admin is None:
                check_password(password, _DUMMY_HASH)
                return _error("invalid_credentials", "Email or password is incorrect.")
            now = timezone.now()
            if admin.locked_until and admin.locked_until > now:
                return _error("locked", "This account is locked after too many failed attempts.")
            if not admin.check_password(password) or not admin.is_active:
                with audit.acting_as("platform_admin", admin.id, admin.email):
                    audit.record("login_failed", admin, using=OWNER, after={"area": "platform"})
                admin.failed_attempts += 1
                if admin.failed_attempts >= 5:
                    admin.locked_until = now + timedelta(minutes=15)
                    admin.failed_attempts = 0
                admin.save(using=OWNER, update_fields=["failed_attempts", "locked_until"])
                return _error("invalid_credentials", "Email or password is incorrect.")
            if admin.totp_secret and not twofactor.verify_code(admin.totp_secret, code):
                return _error("2fa_required" if not code else "invalid_code", "Enter the code from your app.")
            admin.failed_attempts = 0
            admin.locked_until = None
            admin.save(using=OWNER, update_fields=["failed_attempts", "locked_until"])
        with audit.acting_as("platform_admin", admin.id, admin.email):
            audit.record("login", admin, using=OWNER, after={"area": "platform"})
        store = SessionStore()
        store[SESSION_ADMIN_KEY] = str(admin.id)
        store[SESSION_ACTIVITY_KEY] = int(timezone.now().timestamp())
        store.create()
        response = Response({"status": "ok", "me": {"email": admin.email, "full_name": admin.full_name}})
        response.set_cookie(
            COOKIE,
            store.session_key,
            httponly=True,
            samesite="Lax",
            secure=settings.SESSION_COOKIE_SECURE,
            path="/platform/",
        )
        return response


class PlatformLogoutView(PlatformView):
    permission_classes = [AllowAny]

    def post(self, request):
        store = getattr(request._request, "platform_session", None)
        if store is not None:
            store.flush()
        response = Response(status=status.HTTP_204_NO_CONTENT)
        response.delete_cookie(COOKIE, path="/platform/")
        return response


class PlatformMeView(PlatformView):
    def get(self, request):
        return Response({"email": request.user.email, "full_name": request.user.full_name})


class AgencyCreateSerializer(serializers.Serializer):
    name = serializers.CharField(max_length=200)
    code = serializers.SlugField(max_length=40)
    fiscal_year_start_month = serializers.IntegerField(min_value=1, max_value=12, default=1)
    timezone = serializers.CharField(max_length=64, default="Asia/Manila")
    root_level_name = serializers.CharField(max_length=80, default="Agency")


class AgencyListView(PlatformView):
    def get(self, request):
        agencies = Agency.objects.using(OWNER).order_by("name")
        return Response([agency_payload(a) for a in agencies])

    def post(self, request):
        s = AgencyCreateSerializer(data=request.data)
        s.is_valid(raise_exception=True)
        d = s.validated_data
        try:
            agency = services.create_agency(
                name=d["name"],
                code=d["code"],
                fiscal_year_start_month=d["fiscal_year_start_month"],
                timezone_name=d["timezone"],
                root_level_name=d["root_level_name"],
            )
        except services.PlatformError as err:
            return _error(err.code, err.message)
        return Response(agency_payload(agency), status=status.HTTP_201_CREATED)


class AgencyDetailView(PlatformView):
    def get(self, request, agency_id):
        return Response(agency_payload(_get_agency(agency_id)))

    def patch(self, request, agency_id):
        agency = _get_agency(agency_id)
        if "status" in request.data:
            try:
                services.set_agency_status(agency, str(request.data["status"]))
            except services.PlatformError as err:
                return _error(err.code, err.message)
        return Response(agency_payload(agency))


class AgencyAdminCreateView(PlatformView):
    """Create an agency administrator. Returns a one-time temporary password."""

    def post(self, request, agency_id):
        agency = _get_agency(agency_id)
        email = str(request.data.get("email", "")).strip()
        if "@" not in email:
            return _error("invalid_email", "Enter a valid email address.")
        try:
            new = services.create_agency_admin(
                agency, email=email, full_name=str(request.data.get("full_name", ""))
            )
        except services.PlatformError as err:
            return _error(err.code, err.message)
        return Response(
            {"id": str(new.user.id), "email": new.user.email, "temporary_password": new.temporary_password},
            status=status.HTTP_201_CREATED,
        )


class AgencySupportView(PlatformView):
    """Read-only look into an agency's data — only while a support grant is active (P1.7)."""

    def get(self, request, agency_id):
        agency = _get_agency(agency_id)
        grant = services.active_grant(request.user, agency)
        if grant is None:
            return _error(
                "no_support_grant",
                "No active support grant. The agency administrator must grant access first.",
                http=status.HTTP_403_FORBIDDEN,
            )
        audit.record("support_access", agency, using=OWNER, after={"grant_id": str(grant.id)})
        users = User.objects.using(OWNER).filter(agency=agency).order_by("email")
        offices = Office.objects.using(OWNER).filter(agency=agency).order_by("path")
        roles = RoleAssignment.objects.using(OWNER).filter(agency=agency)
        return Response(
            {
                "agency": agency_payload(agency),
                "grant": {"expires_at": grant.expires_at.isoformat(), "reason": grant.reason},
                "users": [
                    {"id": str(u.id), "email": u.email, "full_name": u.full_name, "is_active": u.is_active}
                    for u in users
                ],
                "offices": [
                    {
                        "id": str(o.id),
                        "code": o.code,
                        "name": o.name,
                        "depth": o.depth,
                        "is_active": o.is_active,
                    }
                    for o in offices
                ],
                "role_assignments": roles.count(),
            }
        )

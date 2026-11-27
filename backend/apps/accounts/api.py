"""Authentication API (MASTERPLAN 13: auth/login, auth/logout, auth/2fa, auth/password, me)."""

from django.conf import settings
from django.contrib.auth import logout
from django.core.exceptions import ValidationError as DjangoValidationError
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import ensure_csrf_cookie
from rest_framework import serializers, status
from rest_framework.authentication import SessionAuthentication
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts import ratelimit, services
from apps.accounts.models import RoleAssignment, User
from apps.accounts.permissions import is_agency_admin
from apps.audit import services as audit


class CsrfEnforcedMixin:
    """DRF skips CSRF for anonymous requests; sign-in endpoints need it (login CSRF)."""

    def initial(self, request, *args, **kwargs):
        if request.method not in ("GET", "HEAD", "OPTIONS"):
            SessionAuthentication().enforce_csrf(request)
        super().initial(request, *args, **kwargs)


def auth_error_response(err: services.AuthError, http_status=status.HTTP_400_BAD_REQUEST) -> Response:
    # Returned, not raised: raising through DRF would roll back the failed-attempt counter.
    return Response({"detail": err.message, "code": err.code, **err.extra}, status=http_status)


def password_errors(exc: DjangoValidationError) -> Response:
    return Response(
        {"new_password": list(exc.messages), "code": "weak_password"}, status=status.HTTP_400_BAD_REQUEST
    )


def me_payload(user: User) -> dict:
    agency = user.agency
    roles = list(
        RoleAssignment.objects.filter(user=user).values("id", "office_id", "level").order_by("created_at")
    )
    return {
        "id": str(user.id),
        "email": user.email,
        "full_name": user.full_name,
        # Testing mode never asks for a new password: nobody signs in.
        "must_change_password": user.must_change_password and not settings.LOGIN_DISABLED,
        "login_disabled": settings.LOGIN_DISABLED,
        "has_2fa": user.has_2fa,
        "email_opt_out": user.email_opt_out,
        "is_agency_admin": is_agency_admin(user),
        "agency": {
            "id": str(agency.id),
            "name": agency.name,
            "code": agency.code,
            "timezone": agency.timezone,
            "fiscal_year_start_month": agency.fiscal_year_start_month,
            "logo": bool(agency.logo_key),
            "setup_complete": bool(agency.settings.get("setup_complete")),
        },
        "roles": [{**r, "id": str(r["id"]), "office_id": str(r["office_id"])} for r in roles],
        "licence": licence_payload(),
    }


def licence_payload() -> dict:
    from apps.tenancy import licence

    return licence.payload(User.objects.filter(is_active=True).count())


class LoginSerializer(serializers.Serializer):
    email = serializers.CharField(max_length=254)
    password = serializers.CharField(max_length=256, trim_whitespace=False)


@method_decorator(ensure_csrf_cookie, name="dispatch")
class CsrfView(APIView):
    """GET sets the CSRF cookie so the SPA can make its first POST."""

    permission_classes = [AllowAny]
    authentication_classes: list = []

    def get(self, request):
        return Response({"ok": True})


class LoginView(CsrfEnforcedMixin, APIView):
    permission_classes = [AllowAny]
    authentication_classes: list = []

    def post(self, request):
        s = LoginSerializer(data=request.data)
        s.is_valid(raise_exception=True)
        try:
            ratelimit.check_signin(audit.client_ip(request))
        except ratelimit.RateLimited as err:
            return ratelimit.too_many(err)
        try:
            result = services.check_credentials(s.validated_data["email"], s.validated_data["password"])
        except services.AuthError as err:
            return auth_error_response(err)
        if result.needs_2fa:
            services.remember_pending_2fa(request, result.user)
            return Response({"status": "2fa_required"})
        services.start_session(request, result.user)
        return Response({"status": "ok", "me": me_payload(result.user)})


class LogoutView(APIView):
    permission_classes = [AllowAny]
    allow_pending_password_change = True

    def post(self, request):
        if request.user.is_authenticated:
            audit.record("logout", request.user)
        logout(request)
        return Response(status=status.HTTP_204_NO_CONTENT)


class MeView(APIView):
    allow_pending_password_change = True

    def get(self, request):
        return Response(me_payload(request.user))

    def patch(self, request):
        """Personal preferences: ``email_opt_out`` (no alert emails for me, P11.4)."""
        user = request.user
        if "email_opt_out" in request.data:
            value = request.data["email_opt_out"]
            if not isinstance(value, bool):
                return Response({"email_opt_out": ["Must be true or false."]}, status=400)
            if value != user.email_opt_out:
                user.email_opt_out = value
                user.save(update_fields=["email_opt_out"])
        return Response(me_payload(user))


class ChangePasswordSerializer(serializers.Serializer):
    current_password = serializers.CharField(trim_whitespace=False)
    new_password = serializers.CharField(trim_whitespace=False, max_length=256)


class ChangePasswordView(APIView):
    allow_pending_password_change = True

    def post(self, request):
        s = ChangePasswordSerializer(data=request.data)
        s.is_valid(raise_exception=True)
        try:
            services.change_own_password(
                request, s.validated_data["current_password"], s.validated_data["new_password"]
            )
        except services.AuthError as err:
            return auth_error_response(err)
        except DjangoValidationError as exc:
            return password_errors(exc)
        return Response({"status": "ok", "me": me_payload(request.user)})


class PasswordResetRequestView(CsrfEnforcedMixin, APIView):
    permission_classes = [AllowAny]
    authentication_classes: list = []

    def post(self, request):
        email = str(request.data.get("email", ""))[:254]
        base_url = request.build_absolute_uri("/")
        services.request_password_reset_email(email, base_url)
        # Same answer whether or not the email exists, and whether or not email is configured.
        return Response({"status": "ok"})


class PasswordResetConfirmSerializer(serializers.Serializer):
    agency = serializers.CharField()
    user = serializers.CharField()
    token = serializers.CharField()
    new_password = serializers.CharField(trim_whitespace=False, max_length=256)


class PasswordResetConfirmView(CsrfEnforcedMixin, APIView):
    permission_classes = [AllowAny]
    authentication_classes: list = []

    def post(self, request):
        s = PasswordResetConfirmSerializer(data=request.data)
        s.is_valid(raise_exception=True)
        d = s.validated_data
        try:
            services.confirm_password_reset(d["agency"], d["user"], d["token"], d["new_password"])
        except services.AuthError as err:
            return auth_error_response(err)
        except DjangoValidationError as exc:
            return password_errors(exc)
        return Response({"status": "ok"})

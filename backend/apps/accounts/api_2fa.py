"""Two-factor endpoints: auth/2fa (sign-in step), auth/2fa/setup, auth/2fa/enable, auth/2fa/disable."""

from rest_framework import status
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts import services, twofactor
from apps.accounts.api import CsrfEnforcedMixin, me_payload


def _error(code, message, http=status.HTTP_400_BAD_REQUEST):
    return Response({"detail": message, "code": code}, status=http)


class TwoFactorVerifyView(CsrfEnforcedMixin, APIView):
    """Second sign-in step: ``{"code": "123456"}`` or ``{"recovery_code": "abcde-fghij"}``."""

    permission_classes = [AllowAny]
    authentication_classes: list = []

    def post(self, request):
        user = services.pending_2fa_user(request)
        if user is None:
            return _error("2fa_expired", "Sign in again: the verification step has expired.")
        pending = request.session[services.SESSION_PENDING_2FA_KEY]
        if pending["attempts"] >= twofactor.MAX_2FA_ATTEMPTS:
            request.session.pop(services.SESSION_PENDING_2FA_KEY, None)
            return _error("2fa_expired", "Too many wrong codes. Sign in again.")
        code = str(request.data.get("code", ""))
        recovery = str(request.data.get("recovery_code", ""))
        ok = False
        if code:
            ok = twofactor.verify_code(user.totp_secret, code)
        elif recovery:
            ok = twofactor.use_recovery_code(user, recovery)
            if ok:
                user.save(update_fields=["recovery_codes"])
        if not ok:
            pending["attempts"] += 1
            request.session.modified = True
            return _error("invalid_code", "The code is not correct.")
        services.start_session(request, user)
        return Response(
            {"status": "ok", "me": me_payload(user), "recovery_codes_left": len(user.recovery_codes)}
        )


class TwoFactorSetupView(APIView):
    """Start enrolment: returns a new secret, its otpauth URI and a QR code (SVG)."""

    allow_pending_password_change = False

    def post(self, request):
        if request.user.has_2fa:
            return _error("already_enabled", "Two-factor sign-in is already on.")
        secret = twofactor.new_secret()
        request.session[twofactor.SESSION_SETUP_KEY] = secret
        uri = twofactor.provisioning_uri(secret, request.user.email)
        return Response({"secret": secret, "otpauth_uri": uri, "qr_svg": twofactor.qr_svg(uri)})


class TwoFactorEnableView(APIView):
    def post(self, request):
        secret = request.session.get(twofactor.SESSION_SETUP_KEY)
        if not secret:
            return _error("no_setup", "Start the setup again.")
        if not twofactor.verify_code(secret, str(request.data.get("code", ""))):
            return _error("invalid_code", "The code is not correct. Check the time on your phone.")
        plain, hashes = twofactor.new_recovery_codes()
        user = request.user
        user.totp_secret = secret
        user.recovery_codes = hashes
        user.save(update_fields=["totp_secret", "recovery_codes"])
        del request.session[twofactor.SESSION_SETUP_KEY]
        return Response({"status": "ok", "recovery_codes": plain})


class TwoFactorDisableView(APIView):
    def post(self, request):
        user = request.user
        if not user.check_password(str(request.data.get("password", ""))):
            return _error("wrong_password", "The password is incorrect.")
        user.totp_secret = None
        user.recovery_codes = []
        user.save(update_fields=["totp_secret", "recovery_codes"])
        return Response({"status": "ok"})

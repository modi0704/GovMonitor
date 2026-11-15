"""Sign-in, password and session services (MASTERPLAN P1.4, P1.5).

Sign-in cannot use ``django.contrib.auth.authenticate``: its user lookup would run before any agency
is set, and row-level security would hide every user. Instead the email is resolved through the
``auth_lookup_user`` SECURITY DEFINER function, the agency context is set, and the password is
checked against the (now visible) user row.
"""

import secrets
import string
from dataclasses import dataclass
from datetime import timedelta

from django.conf import settings
from django.contrib.auth import login as django_login
from django.contrib.auth import update_session_auth_hash
from django.contrib.auth.hashers import check_password, make_password
from django.contrib.auth.password_validation import validate_password
from django.contrib.auth.tokens import PasswordResetTokenGenerator
from django.core.mail import send_mail
from django.utils import timezone

from apps.accounts.lookup import lookup_user_by_email
from apps.accounts.models import User
from apps.audit import services as audit
from apps.tenancy import context
from apps.tenancy.middleware import SESSION_AGENCY_KEY
from apps.tenancy.models import Agency

MAX_FAILED_ATTEMPTS = 5
LOCK_MINUTES = 15
SESSION_LAST_ACTIVITY_KEY = "_last_activity"
SESSION_PENDING_2FA_KEY = "_pending_2fa"
PENDING_2FA_SECONDS = 300
_DUMMY_HASH = make_password("timing-equaliser-not-a-real-password")


class AuthError(Exception):
    """A sign-in or password operation was refused. ``code`` is stable for the frontend."""

    def __init__(self, code: str, message: str, **extra):
        super().__init__(message)
        self.code = code
        self.message = message
        self.extra = extra


@dataclass
class SignInResult:
    user: User
    needs_2fa: bool


def _now():
    return timezone.now()


def check_credentials(email: str, password: str) -> SignInResult:
    """Validate email + password; apply the lock rule. Sets the agency context on success.

    Errors never say whether the email exists, except for "locked", which is only reported once the
    password was also checked (so it reveals nothing to someone without the password... and stops
    guessing either way).
    """
    found = lookup_user_by_email(email)
    if found is None:
        check_password(password or "", _DUMMY_HASH)  # same work as a real check
        # Unknown email: no agency to file it under, so it is a platform-level event.
        audit.record(
            "login_failed",
            entity_type="user",
            after={"email": (email or "")[:254], "reason": "unknown_email"},
            using="owner",
        )
        raise AuthError("invalid_credentials", "Email or password is incorrect.")

    context.set_agency(found.agency_id)
    user = User.objects.select_related("agency").select_for_update().get(pk=found.id)
    now = _now()
    if user.locked_until and user.locked_until > now:
        audit.record("login_failed", user, after={"reason": "locked"})
        raise AuthError(
            "locked",
            "This account is locked after too many failed attempts. Try again later.",
            locked_until=user.locked_until.isoformat(),
        )
    if not user.check_password(password or ""):
        user.failed_attempts += 1
        fields = ["failed_attempts"]
        if user.failed_attempts >= MAX_FAILED_ATTEMPTS:
            user.locked_until = now + timedelta(minutes=LOCK_MINUTES)
            user.failed_attempts = 0
            fields.append("locked_until")
        user.save(update_fields=fields)
        audit.record(
            "login_failed",
            user,
            after={"reason": "wrong_password", "locked": "locked_until" in fields},
        )
        raise AuthError("invalid_credentials", "Email or password is incorrect.")
    if not user.is_active:
        audit.record("login_failed", user, after={"reason": "inactive"})
        raise AuthError("inactive", "This account has been deactivated. Contact your administrator.")
    if user.agency.status != Agency.Status.ACTIVE:
        audit.record("login_failed", user, after={"reason": "agency_suspended"})
        raise AuthError("agency_suspended", "Your agency's access is suspended. Contact the vendor.")
    if user.failed_attempts or user.locked_until:
        user.failed_attempts = 0
        user.locked_until = None
        user.save(update_fields=["failed_attempts", "locked_until"])
    return SignInResult(user=user, needs_2fa=user.has_2fa)


def start_session(request, user: User) -> None:
    """Complete sign-in: rotate the session key, bind the session to the user's agency."""
    request.session.pop(SESSION_PENDING_2FA_KEY, None)
    django_login(request, user, backend="django.contrib.auth.backends.ModelBackend")
    request.session[SESSION_AGENCY_KEY] = str(user.agency_id)
    request.session[SESSION_LAST_ACTIVITY_KEY] = int(_now().timestamp())
    audit.record("login", user, after={"two_factor": user.has_2fa})


def remember_pending_2fa(request, user: User) -> None:
    request.session.cycle_key()
    request.session[SESSION_PENDING_2FA_KEY] = {
        "user_id": str(user.id),
        "agency_id": str(user.agency_id),
        "at": int(_now().timestamp()),
        "attempts": 0,
    }


def pending_2fa_user(request) -> User | None:
    data = request.session.get(SESSION_PENDING_2FA_KEY)
    if not data or _now().timestamp() - data["at"] > PENDING_2FA_SECONDS:
        request.session.pop(SESSION_PENDING_2FA_KEY, None)
        return None
    context.set_agency(data["agency_id"])
    return User.objects.filter(pk=data["user_id"], is_active=True).first()


def is_session_idle(request) -> bool:
    last = request.session.get(SESSION_LAST_ACTIVITY_KEY)
    if last is None:
        return False
    return _now().timestamp() - last > settings.SESSION_IDLE_MINUTES * 60


def touch_session(request) -> None:
    request.session[SESSION_LAST_ACTIVITY_KEY] = int(_now().timestamp())


# ---- Passwords --------------------------------------------------------------------------------


def set_new_password(user: User, new_password: str) -> None:
    """Validate against the password rules (min 12 chars + Django validators) and store."""
    validate_password(new_password, user=user)
    user.set_password(new_password)
    user.must_change_password = False
    user.failed_attempts = 0
    user.locked_until = None
    user.save(update_fields=["password", "must_change_password", "failed_attempts", "locked_until"])


def change_own_password(request, current_password: str, new_password: str) -> None:
    user = request.user
    if not user.check_password(current_password or ""):
        raise AuthError("wrong_password", "The current password is incorrect.")
    if current_password == new_password:
        raise AuthError("same_password", "Choose a password different from the current one.")
    set_new_password(user, new_password)
    audit.record("password_change", user)
    update_session_auth_hash(request, user)  # keep this session, sign out the others


def generate_temporary_password(length: int = 16) -> str:
    alphabet = string.ascii_letters + string.digits
    while True:
        pw = "".join(secrets.choice(alphabet) for _ in range(length))
        if any(c.isdigit() for c in pw) and any(c.isalpha() for c in pw):
            return pw


def admin_reset_password(user: User) -> str:
    """Agency administrator resets a user's password: returns a one-time temporary password.

    The user must change it at next sign-in; the lock is cleared. If email is configured the user
    is told by email that the password was reset (the temporary password itself is never emailed).
    """
    temporary = generate_temporary_password()
    user.set_password(temporary)
    user.must_change_password = True
    user.failed_attempts = 0
    user.locked_until = None
    user.save(update_fields=["password", "must_change_password", "failed_attempts", "locked_until"])
    audit.record("password_reset", user, after={"by": "administrator"})
    if settings.EMAIL_ENABLED and not user.email_opt_out:
        send_mail(
            "Your password was reset",
            "An administrator reset your GovMonitor password. Ask them for the temporary password; "
            "you will choose a new one when you sign in.",
            None,
            [user.email],
            fail_silently=True,
        )
    return temporary


token_generator = PasswordResetTokenGenerator()


def request_password_reset_email(email: str, base_url: str) -> None:
    """Self-service reset by email. Silent on unknown emails; sends nothing without SMTP."""
    found = lookup_user_by_email(email)
    if found is None:
        audit.record(
            "password_reset_requested",
            entity_type="user",
            after={"email": (email or "")[:254], "result": "unknown_email"},
            using="owner",
        )
        return
    context.set_agency(found.agency_id)
    user = User.objects.filter(pk=found.id, is_active=True).first()
    if user is None or not settings.EMAIL_ENABLED:
        audit.record(
            "password_reset_requested",
            entity_type="user",
            entity_id=found.id,
            agency_id=found.agency_id,
            after={"result": "inactive_user" if user is None else "email_disabled"},
        )
        return
    audit.record("password_reset_requested", user, after={"result": "email_sent"})
    token = token_generator.make_token(user)
    link = f"{base_url.rstrip('/')}/reset-password?a={user.agency_id}&u={user.id}&t={token}"
    send_mail(
        "Reset your GovMonitor password",
        f"Open this link to choose a new password (valid for a limited time):\n\n{link}\n\n"
        "If you did not ask for this, ignore this message.",
        None,
        [user.email],
        fail_silently=False,
    )


def confirm_password_reset(agency_id: str, user_id: str, token: str, new_password: str) -> User:
    try:
        context.set_agency(agency_id)
        user = User.objects.filter(pk=user_id, is_active=True).first()
    except (ValueError, TypeError):
        user = None
    if user is None or not token_generator.check_token(user, token):
        raise AuthError("invalid_token", "This reset link is invalid or has expired.")
    set_new_password(user, new_password)
    audit.record("password_reset", user, after={"by": "email_link"})
    return user

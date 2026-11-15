from datetime import timedelta

import pytest
from django.core import mail
from django.test import Client
from django.utils import timezone

from apps.accounts import services
from apps.accounts.models import User
from apps.tenancy import context
from apps.tenancy.models import Agency
from apps.tenancy.worker import run_in_agency
from tests.factories import DEFAULT_PASSWORD, make_agency, make_user

pytestmark = pytest.mark.django_db


def login(client, email, password=DEFAULT_PASSWORD):
    return client.post(
        "/api/v1/auth/login", {"email": email, "password": password}, content_type="application/json"
    )


def reload(user):
    return run_in_agency(user.agency_id, lambda: User.objects.get(pk=user.pk))


@pytest.fixture
def agency():
    return make_agency("alpha", "Alpha Agency")


@pytest.fixture
def user(agency):
    return make_user(agency, "ana@alpha.gov", full_name="Ana")


def test_sign_in_and_me_and_sign_out(client, user):
    assert client.get("/api/v1/me").status_code == 401
    r = login(client, "ANA@alpha.gov")
    assert r.status_code == 200, r.json()
    body = r.json()
    assert body["status"] == "ok" and body["me"]["email"] == "ana@alpha.gov"
    assert body["me"]["agency"]["code"] == "alpha"
    me = client.get("/api/v1/me").json()
    assert me["id"] == str(user.id)
    assert reload(user).last_login is not None
    assert client.post("/api/v1/auth/logout").status_code == 204
    assert client.get("/api/v1/me").json()["code"] == "not_authenticated"


@pytest.mark.django_db(databases=["default", "owner"])
def test_wrong_password_and_unknown_email_look_the_same(client, user):
    a = login(client, "ana@alpha.gov", "wrong-password-123")
    b = login(client, "nobody@alpha.gov", "wrong-password-123")
    assert a.status_code == b.status_code == 400
    assert (
        a.json() == b.json() == {"detail": "Email or password is incorrect.", "code": "invalid_credentials"}
    )


def test_lock_after_five_failures_for_fifteen_minutes(client, user):
    for _ in range(4):
        login(client, "ana@alpha.gov", "nope-nope-nope")
    assert reload(user).failed_attempts == 4
    login(client, "ana@alpha.gov", "nope-nope-nope")
    locked = reload(user)
    assert locked.locked_until is not None
    minutes = (locked.locked_until - timezone.now()).total_seconds() / 60
    assert 14 < minutes <= 15
    r = login(client, "ana@alpha.gov")  # even the right password is refused while locked
    assert r.status_code == 400 and r.json()["code"] == "locked"

    def expire():
        User.objects.filter(pk=user.pk).update(locked_until=timezone.now() - timedelta(seconds=1))

    run_in_agency(user.agency_id, expire)
    assert login(client, "ana@alpha.gov").status_code == 200
    assert reload(user).locked_until is None


def test_inactive_user_and_suspended_agency(client, agency, user):
    run_in_agency(agency.id, lambda: User.objects.filter(pk=user.pk).update(is_active=False))
    assert login(client, "ana@alpha.gov").json()["code"] == "inactive"
    run_in_agency(agency.id, lambda: User.objects.filter(pk=user.pk).update(is_active=True))
    assert login(client, "ana@alpha.gov").status_code == 200
    # Suspending the agency ends access for sessions already signed in.
    run_in_agency(agency.id, lambda: Agency.objects.filter(pk=agency.pk).update(status="suspended"))
    assert client.get("/api/v1/me").status_code == 403
    client.post("/api/v1/auth/logout")
    assert login(client, "ana@alpha.gov").json()["code"] == "agency_suspended"


def test_forced_password_change_on_first_sign_in(client, agency):
    make_user(agency, "new@alpha.gov", password="Temporary-pass-1", must_change_password=True)
    r = login(client, "new@alpha.gov", "Temporary-pass-1")
    assert r.json()["me"]["must_change_password"] is True
    assert client.get("/api/v1/me").status_code == 200  # me stays reachable

    weak = client.post(
        "/api/v1/auth/password",
        {"current_password": "Temporary-pass-1", "new_password": "short"},
        content_type="application/json",
    )
    assert weak.status_code == 400 and weak.json()["code"] == "weak_password"
    numeric = client.post(
        "/api/v1/auth/password",
        {"current_password": "Temporary-pass-1", "new_password": "123456789012345"},
        content_type="application/json",
    )
    assert numeric.status_code == 400
    ok = client.post(
        "/api/v1/auth/password",
        {"current_password": "Temporary-pass-1", "new_password": "a-much-better-passphrase"},
        content_type="application/json",
    )
    assert ok.status_code == 200 and ok.json()["me"]["must_change_password"] is False
    assert client.get("/api/v1/me").status_code == 200  # session survives its own password change


def test_idle_timeout_ends_session(client, user, settings):
    settings.SESSION_IDLE_MINUTES = 1
    login(client, "ana@alpha.gov")
    session = client.session
    session[services.SESSION_LAST_ACTIVITY_KEY] = int(timezone.now().timestamp()) - 61
    session.save()
    r = client.get("/api/v1/me")
    assert r.status_code == 401 and r.json()["code"] == "session_expired"


def test_admin_reset_password(client, user, settings):
    settings.EMAIL_ENABLED = True
    temporary = run_in_agency(user.agency_id, lambda: services.admin_reset_password(reload(user)))
    assert len(temporary) == 16
    assert login(client, "ana@alpha.gov").status_code == 400  # old password gone
    r = login(client, "ana@alpha.gov", temporary)
    assert r.json()["me"]["must_change_password"] is True
    assert len(mail.outbox) == 1 and temporary not in mail.outbox[0].body


def test_password_reset_by_email(client, user, settings):
    settings.EMAIL_ENABLED = False
    assert client.post("/api/v1/auth/password-reset", {"email": "ana@alpha.gov"}).json() == {"status": "ok"}
    assert len(mail.outbox) == 0  # no SMTP configured: nothing is sent

    settings.EMAIL_ENABLED = True
    client.post("/api/v1/auth/password-reset", {"email": "nobody@alpha.gov"})
    assert len(mail.outbox) == 0
    client.post("/api/v1/auth/password-reset", {"email": "ana@alpha.gov"})
    assert len(mail.outbox) == 1
    link = next(line for line in mail.outbox[0].body.splitlines() if "reset-password?" in line)
    params = dict(p.split("=", 1) for p in link.split("?", 1)[1].split("&"))
    payload = {
        "agency": params["a"],
        "user": params["u"],
        "token": params["t"],
        "new_password": "brand-new-passphrase",
    }
    assert (
        client.post(
            "/api/v1/auth/password-reset/confirm", payload, content_type="application/json"
        ).status_code
        == 200
    )
    # Token is single-use: the password hash changed.
    again = client.post("/api/v1/auth/password-reset/confirm", payload, content_type="application/json")
    assert again.json()["code"] == "invalid_token"
    assert login(client, "ana@alpha.gov", "brand-new-passphrase").status_code == 200


def test_reset_token_cannot_cross_agencies(client, user):
    other = make_agency("beta")
    token = run_in_agency(user.agency_id, lambda: services.token_generator.make_token(reload(user)))
    payload = {
        "agency": str(other.id),
        "user": str(user.id),
        "token": token,
        "new_password": "brand-new-passphrase",
    }
    r = client.post("/api/v1/auth/password-reset/confirm", payload, content_type="application/json")
    assert r.json()["code"] == "invalid_token"


def test_sign_in_requires_csrf_token(user):
    strict = Client(enforce_csrf_checks=True)
    assert login(strict, "ana@alpha.gov").status_code == 403
    strict.get("/api/v1/auth/csrf")
    token = strict.cookies["gm_csrftoken"].value
    r = strict.post(
        "/api/v1/auth/login",
        {"email": "ana@alpha.gov", "password": DEFAULT_PASSWORD},
        content_type="application/json",
        headers={"X-CSRFToken": token},
    )
    assert r.status_code == 200


def test_session_is_bound_to_its_agency(client, user):
    """A session cannot be pointed at another agency: RLS hides the user and the request is anonymous."""
    other = make_agency("beta")
    login(client, "ana@alpha.gov")
    session = client.session
    session["_agency_id"] = str(other.id)
    session.save()
    assert client.get("/api/v1/me").status_code == 401
    assert context.current_agency_id() is None

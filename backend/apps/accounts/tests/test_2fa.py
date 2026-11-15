import pyotp
import pytest

from apps.accounts.models import User
from apps.tenancy.worker import run_in_agency
from tests.factories import DEFAULT_PASSWORD, make_agency, make_user

pytestmark = pytest.mark.django_db


def post(client, url, data=None):
    return client.post(url, data or {}, content_type="application/json")


def login(client, email="ana@alpha.gov", password=DEFAULT_PASSWORD):
    return post(client, "/api/v1/auth/login", {"email": email, "password": password})


@pytest.fixture
def user():
    return make_user(make_agency("alpha"), "ana@alpha.gov")


def enrol(client):
    login(client)
    setup = post(client, "/api/v1/auth/2fa/setup").json()
    assert setup["otpauth_uri"].startswith("otpauth://totp/GovMonitor:ana%40alpha.gov")
    assert setup["qr_svg"].lstrip().startswith("<?xml") or "<svg" in setup["qr_svg"]
    totp = pyotp.TOTP(setup["secret"])
    assert post(client, "/api/v1/auth/2fa/enable", {"code": "000000"}).json()["code"] == "invalid_code"
    r = post(client, "/api/v1/auth/2fa/enable", {"code": totp.now()})
    assert r.status_code == 200
    codes = r.json()["recovery_codes"]
    assert len(codes) == 10 and len(set(codes)) == 10
    client.post("/api/v1/auth/logout")
    return totp, codes


def test_enrol_then_sign_in_with_code(client, user):
    totp, _ = enrol(client)
    assert login(client).json() == {"status": "2fa_required"}
    assert client.get("/api/v1/me").status_code == 401  # not signed in yet
    assert post(client, "/api/v1/auth/2fa", {"code": "123456"}).json()["code"] == "invalid_code"
    r = post(client, "/api/v1/auth/2fa", {"code": totp.now()})
    assert r.status_code == 200 and r.json()["me"]["has_2fa"] is True
    assert client.get("/api/v1/me").status_code == 200


def test_recovery_codes_are_single_use(client, user):
    _, codes = enrol(client)
    login(client)
    r = post(client, "/api/v1/auth/2fa", {"recovery_code": codes[0].upper()})
    assert r.status_code == 200 and r.json()["recovery_codes_left"] == 9
    client.post("/api/v1/auth/logout")
    login(client)
    assert post(client, "/api/v1/auth/2fa", {"recovery_code": codes[0]}).json()["code"] == "invalid_code"


def test_too_many_wrong_codes_restart_sign_in(client, user):
    totp, _ = enrol(client)
    login(client)
    for _ in range(5):
        post(client, "/api/v1/auth/2fa", {"code": "000000"})
    assert post(client, "/api/v1/auth/2fa", {"code": totp.now()}).json()["code"] == "2fa_expired"


def test_disable_requires_password(client, user):
    totp, _ = enrol(client)
    login(client)
    post(client, "/api/v1/auth/2fa", {"code": totp.now()})
    assert post(client, "/api/v1/auth/2fa/disable", {"password": "wrong"}).status_code == 400
    assert post(client, "/api/v1/auth/2fa/disable", {"password": DEFAULT_PASSWORD}).status_code == 200
    stored = run_in_agency(user.agency_id, lambda: User.objects.get(pk=user.pk))
    assert stored.totp_secret is None and stored.recovery_codes == []
    client.post("/api/v1/auth/logout")
    assert login(client).json()["status"] == "ok"


def test_2fa_step_without_password_step_is_refused(client, user):
    assert post(client, "/api/v1/auth/2fa", {"code": "123456"}).json()["code"] == "2fa_expired"

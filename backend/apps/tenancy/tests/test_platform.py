import pytest
from django.core.management import CommandError, call_command
from django.test import Client

from apps.tenancy.models import Agency, PlatformAdmin

PW = "platform-owner-passphrase"
DBS = ["default", "owner"]


def post(client, url, data=None, method="post"):
    return getattr(client, method)(url, data or {}, content_type="application/json")


@pytest.fixture
def platform_admin(db):
    admin = PlatformAdmin(email="ops@vendor.example", full_name="Ops")
    admin.set_password(PW)
    admin.save(using="owner")
    return admin


def platform_login(client):
    r = post(client, "/platform/api/auth/login", {"email": "ops@vendor.example", "password": PW})
    assert r.status_code == 200, r.content
    return r


@pytest.mark.django_db(databases=DBS, transaction=True)
def test_platform_creates_agency_and_first_admin_who_can_sign_in(platform_admin):
    ops = Client()
    assert ops.get("/platform/api/agencies").status_code in (401, 403)
    platform_login(ops)
    assert ops.cookies["gm_platform"]["path"] == "/platform/"
    r = post(
        ops,
        "/platform/api/agencies",
        {"name": "Bureau of Things", "code": "bot", "fiscal_year_start_month": 7},
    )
    assert r.status_code == 201, r.content
    agency = r.json()
    assert agency["status"] == "active" and agency["fiscal_year_start_month"] == 7
    assert (
        post(ops, "/platform/api/agencies", {"name": "Again", "code": "bot"}).json()["code"]
        == "duplicate_code"
    )

    r = post(
        ops, f"/platform/api/agencies/{agency['id']}/admins", {"email": "Chief@BoT.gov", "full_name": "Chief"}
    )
    assert r.status_code == 201
    temporary = r.json()["temporary_password"]
    assert [a["code"] for a in ops.get("/platform/api/agencies").json()] == ["bot"]

    # The new administrator signs in to the agency side and is the agency administrator.
    user = Client()
    r = post(user, "/api/v1/auth/login", {"email": "chief@bot.gov", "password": temporary})
    me = r.json()["me"]
    assert me["must_change_password"] is True and me["agency"]["code"] == "bot"
    assert len(me["roles"]) == 1 and me["roles"][0]["level"] == "admin"

    # Platform session and agency session are separate.
    assert ops.get("/api/v1/me").status_code == 401
    assert user.get("/platform/api/agencies").status_code in (401, 403)

    # Suspending the agency blocks its users.
    r = post(ops, f"/platform/api/agencies/{agency['id']}", {"status": "suspended"}, method="patch")
    assert r.json()["status"] == "suspended"
    assert user.get("/api/v1/me").status_code == 403


@pytest.mark.django_db(databases=DBS)
def test_platform_login_failures_and_lock(platform_admin):
    c = Client()
    for _ in range(5):
        assert (
            post(c, "/platform/api/auth/login", {"email": "ops@vendor.example", "password": "x"}).status_code
            == 400
        )
    r = post(c, "/platform/api/auth/login", {"email": "ops@vendor.example", "password": PW})
    assert r.json()["code"] == "locked"
    assert post(c, "/platform/api/auth/login", {"email": "who@vendor.example", "password": PW}).json()[
        "code"
    ] == ("invalid_credentials")


@pytest.mark.django_db(databases=DBS)
def test_platform_area_hidden_in_single_mode(platform_admin, settings):
    settings.DEPLOYMENT_MODE = "single"
    c = Client()
    assert (
        post(c, "/platform/api/auth/login", {"email": "ops@vendor.example", "password": PW}).status_code
        == 404
    )
    assert c.get("/platform/api/agencies").status_code == 404


@pytest.mark.django_db(databases=DBS)
def test_app_user_cannot_read_platform_admin_table(platform_admin):
    from django.db import connection
    from django.db.utils import ProgrammingError

    with pytest.raises(ProgrammingError), connection.cursor() as cur:
        cur.execute("SELECT count(*) FROM platform_admin")


@pytest.mark.django_db(databases=DBS, transaction=True)
def test_bootstrap_single_agency_is_idempotent(capsys):
    args = ["--name", "Sample Ministry", "--code", "SAMPLE", "--admin-email", "admin@sample.gov"]
    call_command("bootstrap_single_agency", *args)
    first = capsys.readouterr().out
    assert "agency created" in first and "temporary password" in first
    call_command("bootstrap_single_agency", *args)
    second = capsys.readouterr().out
    assert "agency exists" in second and "administrator exists" in second
    assert Agency.objects.using("owner").count() == 1
    with pytest.raises(CommandError, match="exactly one agency"):
        call_command(
            "bootstrap_single_agency", "--name", "Other", "--code", "other", "--admin-email", "o@o.gov"
        )


@pytest.mark.django_db(databases=DBS)
def test_create_platform_admin_command(capsys):
    call_command("create_platform_admin", "--email", "New@Vendor.example", "--password", PW)
    call_command("create_platform_admin", "--email", "new@vendor.example", "--password", PW + "2")
    assert PlatformAdmin.objects.using("owner").filter(email="new@vendor.example").count() == 1
    with pytest.raises(CommandError):
        call_command("create_platform_admin", "--email", "weak@vendor.example", "--password", "short")

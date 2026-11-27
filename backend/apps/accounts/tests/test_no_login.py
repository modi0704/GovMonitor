"""Testing mode without sign-in (LOGIN_DISABLED): the app opens directly as an administrator."""

import pytest
from django.test import Client

from apps.audit.models import AuditLog
from apps.tenancy import context
from tests.reporting_helpers import reporting_world

pytestmark = pytest.mark.django_db(databases=["default", "owner"], transaction=True)


def csrf_client():
    c = Client(enforce_csrf_checks=True)
    c.get("/api/v1/auth/csrf")
    return c, {"HTTP_X_CSRFTOKEN": c.cookies["gm_csrftoken"].value}


def test_without_the_switch_nobody_is_signed_in(settings):
    reporting_world()
    settings.LOGIN_DISABLED = False
    assert Client().get("/api/v1/me").status_code == 401


def test_testing_mode_acts_as_the_first_administrator(settings):
    w = reporting_world()
    settings.LOGIN_DISABLED = True
    c, csrf = csrf_client()
    me = c.get("/api/v1/me").json()
    assert me["email"] == "boss@alpha.gov" and me["is_agency_admin"] and me["login_disabled"]
    assert me["must_change_password"] is False  # nobody signs in, so nobody is asked
    # Reads and writes work, CSRF still applies, and the change history names the administrator.
    assert c.get("/api/v1/progress").status_code == 200
    r = c.post("/api/v1/offices", {"parent_id": str(w["root"].id), "name": "New", "code": "NEW1"},
               content_type="application/json", **csrf)  # fmt: skip
    assert r.status_code == 201, r.content
    assert c.post("/api/v1/offices", {}, content_type="application/json").status_code == 403  # no CSRF
    with context.agency_context(w["agency"].id):
        assert AuditLog.objects.filter(action="create", actor_label="boss@alpha.gov").exists()


def test_login_as_picks_the_account(settings):
    reporting_world()
    settings.LOGIN_DISABLED = True
    settings.LOGIN_AS = "div@alpha.gov"
    assert Client().get("/api/v1/me").json()["email"] == "div@alpha.gov"
    settings.LOGIN_AS = "nobody@alpha.gov"  # unknown: falls back to the administrator
    assert Client().get("/api/v1/me").json()["email"] == "boss@alpha.gov"


def test_empty_database_still_asks_to_sign_in(settings):
    settings.LOGIN_DISABLED = True
    assert Client().get("/api/v1/me").status_code == 401

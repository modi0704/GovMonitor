"""P3.4: every state-changing API route writes at least one audit row when it succeeds.

Each (route name, method) that can change state needs a scenario below. A new endpoint without a
scenario fails ``test_every_unsafe_route_has_a_scenario``; a scenario whose successful call writes
no audit row fails ``test_successful_unsafe_calls_write_audit_rows``. The response header
``X-Audit-Rows`` (test settings only) counts the rows written by that one request.
"""

import pyotp
import pytest
from django.test import Client
from django.urls import get_resolver

from apps.tenancy.models import PlatformAdmin
from tests.factories import (
    DEFAULT_PASSWORD,
    Json,
    api_client,
    assign,
    make_agency,
    make_office,
    make_root,
    make_user,
)

# Only sign-out (and, from Phase 11, notification-read) may succeed without an audit row.
ALLOW_WITHOUT_AUDIT = {("platform-logout", "POST")}
UNSAFE = ("post", "put", "patch", "delete")
PLATFORM_PW = "platform-owner-passphrase"


def unsafe_routes():
    def walk(patterns):
        for p in patterns:
            if hasattr(p, "url_patterns"):
                yield from walk(p.url_patterns)
            else:
                cls = getattr(p.callback, "view_class", None)
                if cls is not None:
                    for m in UNSAFE:
                        if hasattr(cls, m):
                            yield (p.name, m.upper())

    return sorted(set(walk(get_resolver().url_patterns)))


class World:
    def __init__(self):
        self.agency = make_agency("alpha")
        self.root = make_root(self.agency)
        self.a = make_office(self.root, "A")
        self.b = make_office(self.root, "B")
        self.boss = make_user(self.agency, "boss@alpha.gov")
        assign(self.boss, self.root, "admin")
        self.staff = make_user(self.agency, "staff@alpha.gov")
        self.staff_ra = assign(self.staff, self.a, "read_only")
        self.admin = Json(api_client("boss@alpha.gov"))

    def platform(self):
        ops = PlatformAdmin(email="ops@vendor.example")
        ops.set_password(PLATFORM_PW)
        ops.save(using="owner")
        c = Json(Client())
        r = c.post("/platform/api/auth/login", {"email": "ops@vendor.example", "password": PLATFORM_PW})
        assert r.status_code == 200
        return c

    def new_group(self):
        return self.admin.post("/api/v1/groups", {"name": "G"}).json()["id"]

    def new_level(self):
        self.admin.put("/api/v1/levels", {"names": ["Agency", "Level 1", "Spare"]})
        return [lv for lv in self.admin.get("/api/v1/levels").json() if lv["name"] == "Spare"][0]["id"]


def _login_2fa(w):
    secret = pyotp.random_base32()
    from apps.accounts.models import User
    from apps.tenancy import context

    with context.agency_context(w.agency.id):
        u = User.objects.get(pk=w.staff.pk)
        u.totp_secret = secret
        u.save()
    c = Json(Client())
    c.post("/api/v1/auth/login", {"email": "staff@alpha.gov", "password": DEFAULT_PASSWORD})
    return c.post("/api/v1/auth/2fa", {"code": pyotp.TOTP(secret).now()})


def _enable_2fa(w):
    c = Json(api_client("staff@alpha.gov"))
    secret = c.post("/api/v1/auth/2fa/setup").json()["secret"]
    return c.post("/api/v1/auth/2fa/enable", {"code": pyotp.TOTP(secret).now()})


def _reset_confirm(w):
    from apps.accounts import services
    from apps.accounts.models import User
    from apps.tenancy import context

    with context.agency_context(w.agency.id):
        token = services.token_generator.make_token(User.objects.get(pk=w.staff.pk))
    return Json(Client()).post(
        "/api/v1/auth/password-reset/confirm",
        {
            "agency": str(w.agency.id),
            "user": str(w.staff.id),
            "token": token,
            "new_password": "a-new-long-passphrase",
        },
    )


def _platform_agency(w):
    c = w.platform()
    created = c.post("/platform/api/agencies", {"name": "Other", "code": "other"}).json()
    return c, created["id"]


SCENARIOS = {
    ("auth-login", "POST"): lambda w: Json(Client()).post(
        "/api/v1/auth/login", {"email": "staff@alpha.gov", "password": DEFAULT_PASSWORD}
    ),
    ("auth-logout", "POST"): lambda w: Json(api_client("staff@alpha.gov")).post("/api/v1/auth/logout"),
    ("auth-password", "POST"): lambda w: Json(api_client("staff@alpha.gov")).post(
        "/api/v1/auth/password",
        {"current_password": DEFAULT_PASSWORD, "new_password": "a-new-long-passphrase"},
    ),
    ("auth-password-reset", "POST"): lambda w: Json(Client()).post(
        "/api/v1/auth/password-reset", {"email": "staff@alpha.gov"}
    ),
    ("auth-password-reset-confirm", "POST"): _reset_confirm,
    ("auth-2fa", "POST"): _login_2fa,
    ("auth-2fa-setup", "POST"): lambda w: Json(api_client("staff@alpha.gov")).post("/api/v1/auth/2fa/setup"),
    ("auth-2fa-enable", "POST"): _enable_2fa,
    ("auth-2fa-disable", "POST"): lambda w: Json(api_client("staff@alpha.gov")).post(
        "/api/v1/auth/2fa/disable", {"password": DEFAULT_PASSWORD}
    ),
    ("users", "POST"): lambda w: w.admin.post("/api/v1/users", {"email": "new@alpha.gov"}),
    ("user", "PATCH"): lambda w: w.admin.patch(f"/api/v1/users/{w.staff.id}", {"full_name": "Staff Member"}),
    ("user-reset", "POST"): lambda w: w.admin.post(f"/api/v1/users/{w.staff.id}/reset-password"),
    ("role-assignments", "POST"): lambda w: w.admin.post(
        "/api/v1/role-assignments", {"user_id": str(w.staff.id), "office_id": str(w.b.id), "level": "admin"}
    ),
    ("role-assignment", "PATCH"): lambda w: w.admin.patch(
        f"/api/v1/role-assignments/{w.staff_ra.id}", {"level": "admin"}
    ),
    ("role-assignment", "DELETE"): lambda w: w.admin.delete(f"/api/v1/role-assignments/{w.staff_ra.id}"),
    ("agency", "PATCH"): lambda w: w.admin.patch("/api/v1/agency", {"name": "Alpha Renamed"}),
    ("support-grants", "POST"): lambda w: (
        w.platform(),
        w.admin.post(
            "/api/v1/support-grants",
            {"platform_admin_email": "ops@vendor.example", "hours": 1, "reason": "r"},
        ),
    )[1],
    ("support-grant", "DELETE"): lambda w: (
        w.platform(),
        w.admin.delete(
            "/api/v1/support-grants/"
            + w.admin.post(
                "/api/v1/support-grants",
                {"platform_admin_email": "ops@vendor.example", "hours": 1, "reason": "r"},
            ).json()["id"]
        ),
    )[1],
    ("levels", "PUT"): lambda w: w.admin.put("/api/v1/levels", {"names": ["Ministry", "Division"]}),
    ("level", "PATCH"): lambda w: w.admin.patch(f"/api/v1/levels/{w.new_level()}", {"name": "Renamed"}),
    ("level", "DELETE"): lambda w: w.admin.delete(f"/api/v1/levels/{w.new_level()}"),
    ("offices", "POST"): lambda w: w.admin.post(
        "/api/v1/offices", {"parent_id": str(w.a.id), "name": "N", "code": "N"}
    ),
    ("offices-import", "POST"): lambda w: w.admin.post(
        "/api/v1/offices/import",
        {"parent_id": str(w.a.id), "rows": [{"code": "IM", "name": "Imp", "depth": 0}]},
    ),
    ("offices-reorder", "POST"): lambda w: w.admin.post(
        "/api/v1/offices/reorder", {"parent_id": str(w.root.id), "order": [str(w.b.id), str(w.a.id)]}
    ),
    ("office", "PATCH"): lambda w: w.admin.patch(f"/api/v1/offices/{w.b.id}", {"name": "Bee"}),
    ("office", "DELETE"): lambda w: w.admin.delete(f"/api/v1/offices/{w.b.id}"),
    ("office-move", "POST"): lambda w: w.admin.post(
        f"/api/v1/offices/{w.b.id}/move", {"parent_id": str(w.a.id)}
    ),
    ("groups", "POST"): lambda w: w.admin.post("/api/v1/groups", {"name": "Mainland"}),
    ("group", "PATCH"): lambda w: w.admin.patch(f"/api/v1/groups/{w.new_group()}", {"description": "d"}),
    ("group", "DELETE"): lambda w: w.admin.delete(f"/api/v1/groups/{w.new_group()}"),
    ("group-members", "PUT"): lambda w: w.admin.put(
        f"/api/v1/groups/{w.new_group()}/members", {"office_ids": [str(w.a.id)]}
    ),
    ("platform-login", "POST"): lambda w: (
        w.platform(),
        Json(Client()).post(
            "/platform/api/auth/login", {"email": "ops@vendor.example", "password": PLATFORM_PW}
        ),
    )[1],
    ("platform-logout", "POST"): lambda w: w.platform().post("/platform/api/auth/logout"),
    ("platform-agencies", "POST"): lambda w: w.platform().post(
        "/platform/api/agencies", {"name": "N", "code": "n"}
    ),
    ("platform-agency", "PATCH"): lambda w: (
        lambda c_id: c_id[0].patch(f"/platform/api/agencies/{c_id[1]}", {"status": "suspended"})
    )(_platform_agency(w)),
    ("platform-agency-admins", "POST"): lambda w: (
        lambda c_id: c_id[0].post(f"/platform/api/agencies/{c_id[1]}/admins", {"email": "chief@other.gov"})
    )(_platform_agency(w)),
}


def test_every_unsafe_route_has_a_scenario():
    missing = [r for r in unsafe_routes() if r not in SCENARIOS]
    assert not missing, f"add audit scenarios to tests/test_audit_coverage.py for: {missing}"


# Scenarios that need rows committed by the owner connection to be visible to app_user.
NEEDS_COMMIT = {("support-grants", "POST"), ("support-grant", "DELETE")}


def _check(route):
    w = World()
    response = SCENARIOS[route](w)
    assert 200 <= response.status_code < 300, (
        f"{route} scenario did not succeed: {response.status_code} {response.content[:200]}"
    )
    if route not in ALLOW_WITHOUT_AUDIT:
        assert int(response["X-Audit-Rows"]) >= 1, f"{route} succeeded without writing an audit row"


@pytest.mark.django_db(databases=["default", "owner"])
@pytest.mark.parametrize("route", sorted(set(SCENARIOS) - NEEDS_COMMIT), ids=lambda r: f"{r[0]}:{r[1]}")
def test_successful_unsafe_calls_write_audit_rows(route):
    _check(route)


@pytest.mark.django_db(databases=["default", "owner"], transaction=True)
@pytest.mark.parametrize("route", sorted(NEEDS_COMMIT), ids=lambda r: f"{r[0]}:{r[1]}")
def test_successful_unsafe_calls_write_audit_rows_committed(route):
    _check(route)

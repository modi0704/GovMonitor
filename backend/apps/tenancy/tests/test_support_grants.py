from datetime import timedelta

import pytest
from django.test import Client
from django.utils import timezone

from apps.tenancy.models import PlatformAdmin, SupportGrant
from tests.factories import DEFAULT_PASSWORD, assign, make_agency, make_office, make_root, make_user

PW = "platform-owner-passphrase"


def post(client, url, data=None):
    return client.post(url, data or {}, content_type="application/json")


@pytest.fixture
def setup(db):
    ops = PlatformAdmin(email="ops@vendor.example")
    ops.set_password(PW)
    ops.save(using="owner")
    agency = make_agency("alpha", "Alpha")
    root = make_root(agency)
    div = make_office(root, "DIV")
    boss = make_user(agency, "boss@alpha.gov")
    assign(boss, root, "admin")
    head = make_user(agency, "head@alpha.gov")
    assign(head, div, "admin")
    return ops, agency, boss, head


def signed_in(email):
    c = Client()
    assert post(c, "/api/v1/auth/login", {"email": email, "password": DEFAULT_PASSWORD}).status_code == 200
    return c


def platform_client():
    c = Client()
    assert (
        post(c, "/platform/api/auth/login", {"email": "ops@vendor.example", "password": PW}).status_code
        == 200
    )
    return c


@pytest.mark.django_db(databases=["default", "owner"], transaction=True)
def test_support_access_requires_an_active_grant(setup):
    ops, agency, boss, head = setup
    vendor = platform_client()
    support_url = f"/platform/api/agencies/{agency.id}/support"
    r = vendor.get(support_url)
    assert r.status_code == 403 and r.json()["code"] == "no_support_grant"

    # Only the agency administrator may grant.
    assert post(signed_in("head@alpha.gov"), "/api/v1/support-grants", {}).status_code == 403

    admin = signed_in("boss@alpha.gov")
    bad = post(
        admin,
        "/api/v1/support-grants",
        {"platform_admin_email": "nobody@vendor.example", "hours": 4, "reason": "x"},
    )
    assert bad.status_code == 400
    r = post(
        admin,
        "/api/v1/support-grants",
        {"platform_admin_email": "OPS@vendor.example", "hours": 4, "reason": "Ticket 42"},
    )
    assert r.status_code == 201, r.content
    grant = r.json()
    assert grant["active"] and grant["platform_admin_email"] == "ops@vendor.example"
    assert grant["granted_by"] == "boss@alpha.gov"

    data = vendor.get(support_url).json()
    assert {u["email"] for u in data["users"]} == {"boss@alpha.gov", "head@alpha.gov"}
    assert len(data["offices"]) == 2

    # Revoking ends access immediately.
    assert admin.delete(f"/api/v1/support-grants/{grant['id']}").json()["active"] is False
    assert vendor.get(support_url).status_code == 403
    assert [g["active"] for g in admin.get("/api/v1/support-grants").json()] == [False]


@pytest.mark.django_db(databases=["default", "owner"], transaction=True)
def test_expired_grant_gives_no_access(setup):
    ops, agency, boss, _ = setup
    SupportGrant(
        agency_id=agency.id,
        platform_admin_id=ops.id,
        granted_by_id=boss.id,
        reason="old",
        expires_at=timezone.now() - timedelta(minutes=1),
    ).save(using="owner")
    assert platform_client().get(f"/platform/api/agencies/{agency.id}/support").status_code == 403


@pytest.mark.django_db(databases=["default", "owner"], transaction=True)
def test_grant_of_one_agency_does_not_open_another(setup):
    ops, agency, boss, _ = setup
    other = make_agency("beta")
    make_root(other)
    post(
        signed_in("boss@alpha.gov"),
        "/api/v1/support-grants",
        {"platform_admin_email": "ops@vendor.example", "hours": 1, "reason": "r"},
    )
    assert platform_client().get(f"/platform/api/agencies/{other.id}/support").status_code == 403

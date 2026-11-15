"""P3.3: sign-in, role changes, structure changes and support grants are audited."""

import pytest
from django.test import Client

from apps.audit.models import AuditLog
from apps.tenancy import context
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

DBS = ["default", "owner"]


def actions(agency):
    with context.agency_context(agency.id):
        return list(AuditLog.objects.order_by("id").values_list("action", "entity_type", "actor_label"))


@pytest.fixture
def world(db):
    agency = make_agency("alpha")
    root = make_root(agency)
    a, b = make_office(root, "A"), make_office(root, "B")
    boss = make_user(agency, "boss@alpha.gov")
    assign(boss, root, "admin")
    staff = make_user(agency, "staff@alpha.gov")
    return {"agency": agency, "root": root, "a": a, "b": b, "boss": boss, "staff": staff}


@pytest.mark.django_db(databases=DBS)
def test_sign_in_success_and_failures(world):
    c = Client()
    c.post(
        "/api/v1/auth/login",
        {"email": "staff@alpha.gov", "password": "wrong"},
        content_type="application/json",
    )
    c.post(
        "/api/v1/auth/login", {"email": "ghost@alpha.gov", "password": "x"}, content_type="application/json"
    )
    c.post(
        "/api/v1/auth/login",
        {"email": "staff@alpha.gov", "password": DEFAULT_PASSWORD},
        content_type="application/json",
    )
    c.post("/api/v1/auth/logout")
    events = [(a, e) for a, e, _ in actions(world["agency"]) if a in ("login", "login_failed", "logout")]
    assert events == [("login_failed", "user"), ("login", "user"), ("logout", "user")]
    ghost = AuditLog.objects.using("owner").get(agency__isnull=True, action="login_failed")
    assert ghost.after == {"email": "ghost@alpha.gov", "reason": "unknown_email"}


def test_role_and_structure_changes(world):
    boss = Json(api_client("boss@alpha.gov"))
    boss.post(
        "/api/v1/role-assignments",
        {"user_id": str(world["staff"].id), "office_id": str(world["a"].id), "level": "admin"},
    )
    boss.post(f"/api/v1/offices/{world['a'].id}/move", {"parent_id": str(world["b"].id)})
    boss.post("/api/v1/offices/reorder", {"parent_id": str(world["root"].id), "order": [str(world["b"].id)]})
    boss.patch(f"/api/v1/offices/{world['b'].id}", {"is_active": False})
    boss.patch(f"/api/v1/offices/{world['b'].id}", {"name": "Bee"})
    got = [(a, e) for a, e, actor in actions(world["agency"]) if actor == "boss@alpha.gov"]
    assert ("role_change", "role_assignment") in got
    assert ("move", "office") in got and ("reorder", "office") in got
    assert ("deactivate", "office") in got and ("update", "office") in got
    with context.agency_context(world["agency"].id):
        move = AuditLog.objects.get(action="move")
        assert move.before == {"parent_id": str(world["root"].id)}
        assert move.after == {"parent_id": str(world["b"].id), "offices_moved": 1}
        deact = AuditLog.objects.get(action="deactivate")
        assert set(deact.after["offices"]) == {str(world["a"].id), str(world["b"].id)}


@pytest.mark.django_db(databases=DBS, transaction=True)
def test_support_grant_and_platform_access_are_audited(world):
    ops = PlatformAdmin(email="ops@vendor.example")
    ops.set_password("platform-owner-passphrase")
    ops.save(using="owner")
    boss = Json(api_client("boss@alpha.gov"))
    boss.post(
        "/api/v1/support-grants",
        {"platform_admin_email": "ops@vendor.example", "hours": 2, "reason": "Ticket 7"},
    )
    vendor = Client()
    vendor.post(
        "/platform/api/auth/login",
        {"email": "ops@vendor.example", "password": "platform-owner-passphrase"},
        content_type="application/json",
    )
    vendor.get(f"/platform/api/agencies/{world['agency'].id}/support")
    got = actions(world["agency"])
    assert ("support_grant", "support_grant", "boss@alpha.gov") in got
    assert ("support_access", "agency", "ops@vendor.example") in got
    platform = AuditLog.objects.using("owner").get(agency__isnull=True, action="login")
    assert (platform.actor_type, platform.actor_label) == ("platform_admin", "ops@vendor.example")

"""Scope enforcement across the office-bound API (P2.6, Phase 2 exit check).

Users: the agency administrator (root admin), a mid-level admin of SVC1, a read-only user of SVC1.
SVC2 is a sibling of SVC1, outside the mid-level users' scope.
"""

import pytest

from apps.accounts.models import RoleAssignment
from apps.accounts.permissions import filter_by_scope
from apps.tenancy import context
from tests.factories import Json, api_client, assign, make_agency, make_office, make_root, make_user

pytestmark = pytest.mark.django_db


@pytest.fixture
def w():
    agency = make_agency("alpha")
    root = make_root(agency)
    svc1, svc2 = make_office(root, "SVC1"), make_office(root, "SVC2")
    div1, div2 = make_office(svc1, "DIV1"), make_office(svc2, "DIV2")
    for email, office, level in [
        ("boss@a.gov", root, "admin"),
        ("mid@a.gov", svc1, "admin"),
        ("ro@a.gov", svc1, "read_only"),
    ]:
        assign(make_user(agency, email), office, level)
    return {"agency": agency, "root": root, "svc1": svc1, "svc2": svc2, "div1": div1, "div2": div2}


def statuses(email, w):
    c = Json(api_client(email))
    own, sibling = w["div1"].id, w["div2"].id
    return {
        "view own": c.get(f"/api/v1/offices/{own}").status_code,
        "view sibling": c.get(f"/api/v1/offices/{sibling}").status_code,
        "rename own": c.patch(f"/api/v1/offices/{own}", {"name": "x"}).status_code,
        "rename sibling": c.patch(f"/api/v1/offices/{sibling}", {"name": "x"}).status_code,
        "add under sibling": c.post(
            "/api/v1/offices", {"parent_id": str(sibling), "name": "n", "code": f"N-{email[:3]}"}
        ).status_code,
    }


def test_agency_admin_can_view_and_edit_everything(w):
    assert statuses("boss@a.gov", w) == {
        "view own": 200,
        "view sibling": 200,
        "rename own": 200,
        "rename sibling": 200,
        "add under sibling": 201,
    }


def test_mid_level_admin_cannot_see_or_edit_a_sibling(w):
    # Structure changes are for the agency administrator only (6.6) -> 403 for every change;
    # reading a sibling's office is out of scope -> 404.
    assert statuses("mid@a.gov", w) == {
        "view own": 200,
        "view sibling": 404,
        "rename own": 403,
        "rename sibling": 403,
        "add under sibling": 403,
    }


def test_read_only_user_views_only_in_scope(w):
    assert statuses("ro@a.gov", w) == {
        "view own": 200,
        "view sibling": 404,
        "rename own": 403,
        "rename sibling": 403,
        "add under sibling": 403,
    }


def test_filter_by_scope_helper_view_vs_edit(w):
    from apps.accounts.models import User

    with context.agency_context(w["agency"].id):
        mid = User.objects.get(email="mid@a.gov")
        ro = User.objects.get(email="ro@a.gov")
        rows = RoleAssignment.objects.all()
        # Role assignments are office-bound rows: each user's view is limited to its scope.
        assert {r.office.code for r in filter_by_scope(rows, mid)} == {"SVC1"}
        assert {r.office.code for r in filter_by_scope(rows, ro, edit=True)} == set()
        assert {r.office.code for r in filter_by_scope(rows, ro)} == {"SVC1"}

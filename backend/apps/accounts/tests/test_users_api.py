import pytest

from tests.factories import Json, api_client, assign, make_agency, make_office, make_root, make_user

pytestmark = pytest.mark.django_db


@pytest.fixture
def world():
    agency = make_agency("alpha")
    root = make_root(agency)
    svc = make_office(root, "SVC")
    div = make_office(svc, "DIV")
    other = make_office(root, "OTHER")
    boss = make_user(agency, "boss@alpha.gov")
    boss_ra = assign(boss, root, "admin")
    head = make_user(agency, "head@alpha.gov")
    assign(head, svc, "admin")
    return {
        "root": root,
        "svc": svc,
        "div": div,
        "other": other,
        "boss": boss,
        "boss_ra": boss_ra,
        "head": head,
    }


def test_only_agency_admin_manages_users(world):
    head = Json(api_client("head@alpha.gov"))
    assert head.get("/api/v1/users").status_code == 403
    assert head.post("/api/v1/users", {"email": "x@alpha.gov"}).status_code == 403


def test_create_user_with_assignment_and_effective_scope(world):
    boss = Json(api_client("boss@alpha.gov"))
    r = boss.post(
        "/api/v1/users",
        {
            "email": "New@Alpha.gov",
            "full_name": "New Person",
            "assignments": [{"office_id": str(world["svc"].id), "level": "read_only"}],
        },
    )
    assert r.status_code == 201, r.content
    new = r.json()
    assert new["email"] == "new@alpha.gov" and len(new["temporary_password"]) == 16
    assert new["assignments"][0]["office"]["code"] == "SVC" and not new["is_agency_admin"]
    assert boss.post("/api/v1/users", {"email": "new@alpha.gov"}).status_code == 400
    scope = boss.get(f"/api/v1/users/{new['id']}/scope").json()
    assert [(o["code"], o["can_edit"]) for o in scope] == [("SVC", False), ("DIV", False)]

    # Promote to admin of DIV only; scope edit flags follow.
    boss.post(
        "/api/v1/role-assignments",
        {"user_id": new["id"], "office_id": str(world["div"].id), "level": "admin"},
    )
    scope = {o["code"]: o["can_edit"] for o in boss.get(f"/api/v1/users/{new['id']}/scope").json()}
    assert scope == {"SVC": False, "DIV": True}

    # The new user signs in with the temporary password and must change it.
    c = Json(api_client("new@alpha.gov", new["temporary_password"]))
    assert c.get("/api/v1/me").json()["must_change_password"] is True
    assert c.get("/api/v1/offices").status_code == 403  # nothing else until the password is changed


def test_reset_deactivate_and_last_admin_guard(world):
    boss = Json(api_client("boss@alpha.gov"))
    head_id = str(world["head"].id)
    temp = boss.post(f"/api/v1/users/{head_id}/reset-password").json()["temporary_password"]
    assert Json(api_client("head@alpha.gov", temp)).get("/api/v1/me").json()["must_change_password"]
    assert boss.patch(f"/api/v1/users/{head_id}", {"is_active": False}).json()["is_active"] is False

    me_id = str(world["boss"].id)
    assert boss.patch(f"/api/v1/users/{me_id}", {"is_active": False}).json()["code"] == "self"
    ra = str(world["boss_ra"].id)
    assert boss.delete(f"/api/v1/role-assignments/{ra}").json()["code"] == "last_admin"
    assert boss.patch(f"/api/v1/role-assignments/{ra}", {"level": "read_only"}).json()["code"] == "last_admin"

    # With a second agency administrator the first one can step down.
    boss.post(
        "/api/v1/role-assignments", {"user_id": head_id, "office_id": str(world["root"].id), "level": "admin"}
    )
    boss.patch(f"/api/v1/users/{head_id}", {"is_active": True})
    assert boss.patch(f"/api/v1/role-assignments/{ra}", {"level": "read_only"}).json()["level"] == "read_only"


def test_users_of_another_agency_are_invisible(world):
    other = make_agency("beta")
    stranger = make_user(other, "x@beta.gov")
    boss = Json(api_client("boss@alpha.gov"))
    assert boss.get(f"/api/v1/users/{stranger.id}").status_code == 404
    assert boss.post(f"/api/v1/users/{stranger.id}/reset-password").status_code == 404
    assert "x@beta.gov" not in {u["email"] for u in boss.get("/api/v1/users").json()}

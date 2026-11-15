import pytest

from tests.factories import Json, api_client, assign, make_agency, make_office, make_root, make_user

pytestmark = pytest.mark.django_db


@pytest.fixture
def world():
    agency = make_agency("alpha", "Alpha Ministry")
    root = make_root(agency, code="MIN", level_name="Ministry")
    svc1 = make_office(root, "SVC1", level_name="Service")
    svc2 = make_office(root, "SVC2")
    div = make_office(svc1, "DIV1", level_name="Division")
    boss = make_user(agency, "boss@alpha.gov")
    assign(boss, root, "admin")
    head = make_user(agency, "head@alpha.gov")
    assign(head, svc1, "admin")
    viewer = make_user(agency, "viewer@alpha.gov")
    assign(viewer, svc1, "read_only")
    return {"agency": agency, "root": root, "svc1": svc1, "svc2": svc2, "div": div}


def test_tree_in_one_call_scoped_by_user(world):
    boss = Json(api_client("boss@alpha.gov"))
    rows = boss.get("/api/v1/offices").json()
    assert [r["code"] for r in rows] == ["MIN", "SVC1", "DIV1", "SVC2"]
    assert rows[0]["parent_id"] is None and rows[2]["depth"] == 2 and all(r["can_edit"] for r in rows)
    head = Json(api_client("head@alpha.gov"))
    assert [r["code"] for r in head.get("/api/v1/offices").json()] == ["SVC1", "DIV1"]
    viewer = Json(api_client("viewer@alpha.gov"))
    assert [r["can_edit"] for r in viewer.get("/api/v1/offices").json()] == [False, False]


def test_admin_builds_and_edits_structure(world):
    boss = Json(api_client("boss@alpha.gov"))
    r = boss.post(
        "/api/v1/offices", {"parent_id": str(world["svc2"].id), "name": "Division 2", "code": "DIV2"}
    )
    assert r.status_code == 201 and r.json()["level"]["depth"] == 2
    div2 = r.json()["id"]
    assert (
        boss.post(
            "/api/v1/offices", {"parent_id": str(world["svc2"].id), "name": "X", "code": "div2"}
        ).json()["code"]
        == "duplicate_code"
    )
    assert (
        boss.patch(f"/api/v1/offices/{div2}", {"name": "Planning Division"}).json()["name"]
        == "Planning Division"
    )
    moved = boss.post(f"/api/v1/offices/{div2}/move", {"parent_id": str(world["svc1"].id)}).json()
    assert moved["parent_id"] == str(world["svc1"].id)
    cyc = boss.post(f"/api/v1/offices/{world['svc1'].id}/move", {"parent_id": div2})
    assert cyc.status_code == 400 and cyc.json()["code"] == "cycle"
    assert (
        boss.post(
            "/api/v1/offices/reorder",
            {"parent_id": str(world["root"].id), "order": [str(world["svc2"].id), str(world["svc1"].id)]},
        ).status_code
        == 204
    )
    assert [r["code"] for r in boss.get("/api/v1/offices").json()][:2] == ["MIN", "SVC2"]
    assert boss.patch(f"/api/v1/offices/{div2}", {"is_active": False}).json()["is_active"] is False
    assert boss.delete(f"/api/v1/offices/{div2}").status_code == 204
    detail = boss.get(f"/api/v1/offices/{world['div'].id}").json()
    assert [a["code"] for a in detail["ancestors"]] == ["MIN", "SVC1"]


def test_levels_api(world):
    boss = Json(api_client("boss@alpha.gov"))
    levels = boss.get("/api/v1/levels").json()
    assert [(lv["depth"], lv["name"], lv["office_count"]) for lv in levels] == [
        (0, "Ministry", 1),
        (1, "Service", 2),
        (2, "Division", 1),
    ]
    r = boss.put("/api/v1/levels", {"names": ["Ministry", "Bureau", "Division", "Unit"]})
    assert [lv["name"] for lv in r.json()] == ["Ministry", "Bureau", "Division", "Unit"]
    unit = r.json()[3]["id"]
    assert boss.delete(f"/api/v1/levels/{r.json()[1]['id']}").json()["code"] in (
        "level_in_use",
        "level_not_last",
    )
    assert boss.delete(f"/api/v1/levels/{unit}").status_code == 204


def test_groups_api(world):
    boss = Json(api_client("boss@alpha.gov"))
    g = boss.post("/api/v1/groups", {"name": "Mainland"}).json()
    assert boss.post("/api/v1/groups", {"name": "mainland"}).status_code == 400
    r = boss.put(
        f"/api/v1/groups/{g['id']}/members", {"office_ids": [str(world["svc1"].id), str(world["svc2"].id)]}
    )
    assert [m["code"] for m in r.json()["members"]] == ["SVC1", "SVC2"]
    assert (
        boss.patch(f"/api/v1/groups/{g['id']}", {"description": "Centers"}).json()["description"] == "Centers"
    )
    # A mid-level admin sees the group but only its members within scope, and cannot change it.
    head = Json(api_client("head@alpha.gov"))
    assert [m["code"] for m in head.get("/api/v1/groups").json()[0]["members"]] == ["SVC1"]
    assert head.put(f"/api/v1/groups/{g['id']}/members", {"office_ids": []}).status_code == 403
    assert boss.delete(f"/api/v1/groups/{g['id']}").status_code == 204

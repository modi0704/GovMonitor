"""A small agency with an approved plan, ready for monthly reporting tests (Phase 6+)."""

from django.core.files.uploadedfile import SimpleUploadedFile

from tests.factories import Json, api_client, assign, make_agency, make_office, make_root, make_user
from tests.plan_helpers import worked_example_rows

PDF = b"%PDF-1.4\n1 0 obj<<>>endobj\ntrailer<<>>\n%%EOF\n"
PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 32


def pdf(name="proof.pdf", content=PDF):
    return SimpleUploadedFile(name, content, content_type="application/pdf")


def reporting_world(code="alpha"):
    """root ─ DIV (owns the plan; activity A is implemented by UNIT) ─ UNIT (field unit)
    └ OTHER"""
    agency = make_agency(code)
    root = make_root(agency)
    div = make_office(root, "DIV")
    unit = make_office(div, "UNIT")
    other = make_office(root, "OTHER")
    for email, office, level in [
        (f"boss@{code}.gov", root, "admin"),
        (f"div@{code}.gov", div, "admin"),
        (f"viewer@{code}.gov", div, "read_only"),
        (f"other@{code}.gov", other, "admin"),
    ]:
        assign(make_user(agency, email), office, level)
    # The field-unit admin is assigned to UNIT only: outside the division's own scope.
    assign(make_user(agency, f"unit@{code}.gov"), unit, "admin")
    boss = Json(api_client(f"boss@{code}.gov"))
    fy = boss.post("/api/v1/fiscal-years", {"label": "2026", "start_year": 2026}).json()
    boss.patch(f"/api/v1/fiscal-years/{fy['id']}", {"status": "open"})
    plan = boss.post("/api/v1/plans", {"office_id": str(div.id), "fiscal_year_id": fy["id"]}).json()
    rows = worked_example_rows()
    rows[1]["implementing_office_id"] = str(unit.id)  # activity A is carried out by the field unit
    saved = boss.post(f"/api/v1/plans/{plan['id']}/save", {"rows": rows}).json()["plan"]
    boss.post(f"/api/v1/plans/{plan['id']}/submit")
    boss.post(f"/api/v1/plans/{plan['id']}/approve")
    acts = {r["code"]: r for r in saved["rows"] if r["row_kind"] == "activity"}
    periods = boss.get(f"/api/v1/fiscal-years/{fy['id']}").json()["periods"]
    return {
        "agency": agency,
        "root": root,
        "div": div,
        "unit": unit,
        "other": other,
        "boss": boss,
        "fy": fy,
        "plan": plan,
        "acts": acts,
        "periods": {p["month_index"]: p for p in periods},
        "code": code,
    }


def client(world, who):
    return Json(api_client(f"{who}@{world['code']}.gov"))


def upload(client_json, world, act="B", month=1, file=None, target_type="activity_actual"):
    return client_json.c.post(
        "/api/v1/attachments",
        {
            "target_type": target_type,
            "lineage_id": world["acts"][act]["lineage_id"],
            "period_id": world["periods"][month]["id"],
            "description": "photo",
            "file": file or pdf(),
        },
    )

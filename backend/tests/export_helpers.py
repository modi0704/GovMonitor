"""Worlds for the Excel export tests (P9.2–P9.8): the 8.1 worked example and the RDI fixture,
both entered through the public API."""

import io
import json
from pathlib import Path

from apps.exports import scope as export_scope
from apps.exports import xlsx_writer
from apps.tenancy import context
from seed.plans import fixture_plans
from tests.factories import Json, api_client, assign, make_agency, make_office, make_root, make_user
from tests.reporting_helpers import reporting_world

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures"
WORKED_ACTUALS = {"A": ["2", "2", "4"], "B": ["0", "1", "3"], "C": ["0", "0", "0"]}


def worked_example_world(months=3, profile=None):
    """reporting_world with the 8.1 actuals for January..``months``. ``profile``: fields to PATCH."""
    w = reporting_world()
    boss = w["boss"]
    if profile:
        fy = boss.get(f"/api/v1/fiscal-years/{w['fy']['id']}").json()
        r = boss.patch(f"/api/v1/scoring-profiles/{fy['profile_id']}", {**profile, "confirm": True})
        assert r.status_code == 200, r.content
    for m in range(1, months + 1):
        acts = [
            {"lineage_id": w["acts"][c]["lineage_id"], "actual": v[m - 1]} for c, v in WORKED_ACTUALS.items()
        ]
        r = boss.post(
            "/api/v1/reports/save",
            {"office": str(w["div"].id), "period": w["periods"][m]["id"], "activities": acts},
        )
        assert r.status_code == 200, r.content
    return w


OUTLINE_KINDS = ("outcome", "outcome_indicator", "output", "output_indicator", "program", "project")


def with_outline(rows):
    """The plan rows under one generic outline chain (outcome → … → project), for layout tests."""
    outline, parent = [], None
    for depth, kind in enumerate(OUTLINE_KINDS):
        key = f"outline-{kind}"
        outline.append(
            {"client_key": key, "parent": parent, "row_kind": kind, "code": f"X{depth + 1}.",
             "title": kind.replace("_", " ").title(), "sort_order": -100 + depth}
        )  # fmt: skip
        parent = key
    return outline + [{**r, "parent": parent} for r in rows]


def rdi_world(outline=False, indicators=None):
    """One office RDI with the MOST FY2023 RDI plan and its twelve months of accomplishments
    (``outline``: placed under a generic outcome → project chain)."""
    agency = make_agency("most")
    root = make_root(agency)
    rds = make_office(root, "RDS")
    rdi = make_office(rds, "RDI")
    assign(make_user(agency, "boss@most.gov"), root, "admin")
    api = Json(api_client("boss@most.gov"))
    fy = api.post("/api/v1/fiscal-years", {"label": "2023", "start_year": 2023}).json()
    api.patch(f"/api/v1/fiscal-years/{fy['id']}", {"status": "open"})
    periods = {p["month_index"]: p for p in api.get(f"/api/v1/fiscal-years/{fy['id']}").json()["periods"]}
    rows = fixture_plans()["RDI"]
    if outline:
        rows = with_outline(rows)
    plan = api.post("/api/v1/plans", {"office_id": str(rdi.id), "fiscal_year_id": fy["id"]}).json()
    saved = api.post(
        f"/api/v1/plans/{plan['id']}/save", {"rows": rows, "indicators": indicators or []}
    ).json()["plan"]
    lineage = {r["code"]: r["lineage_id"] for r in saved["rows"]}
    api.post(f"/api/v1/plans/{plan['id']}/submit")
    api.post(f"/api/v1/plans/{plan['id']}/approve")
    data = json.loads((FIXTURES / "most_fy2023_rdi.json").read_text())
    for month in range(1, 13):
        acts = [
            {"lineage_id": lineage[f"RDI-{i}"], "actual": a["actual"][month - 1]}
            for i, a in enumerate(data["activities"], start=1)
        ]
        r = api.post(
            "/api/v1/reports/save",
            {"office": str(rdi.id), "period": periods[month]["id"], "activities": acts},
        )
        assert r.status_code == 200, r.content
    return {"agency": agency, "root": root, "rds": rds, "rdi": rdi, "api": api, "fy": fy, "periods": periods,
            "plan": plan, "rows": rows, "data": data}  # fmt: skip


def build(agency, office, period_id, scope="office", view="owner"):
    """(workbook bytes, ExportScope) for one export, run directly (no job)."""
    with context.agency_context(agency.id):
        sc = export_scope.resolve(
            {"scope": scope, "office_id": str(office.id), "period_id": period_id, "view": view}
        )
        data, _ = xlsx_writer.build(sc)
    return io.BytesIO(data), sc

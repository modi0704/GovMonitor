"""The MOST December 2023 figures (MASTERPLAN 8.2) reproduced by the application, end to end:
plans loaded through the plan API, twelve months of accomplishments entered through the reporting
API, results read from the live results service. Skipped when the P4.2 fixtures are absent."""

import json
from decimal import Decimal as D
from pathlib import Path

import pytest

from apps.planning.models import Plan
from apps.results import services as results
from apps.scoring import engine
from apps.tenancy import context
from seed.plans import fixture_plans
from tests.factories import Json, api_client, assign, make_agency, make_office, make_root, make_user

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures"
EXPECTED = {
    "PME": "0.9583",
    "HRM": "0.8368",
    "RDI": "0.9907",
    "AST": "0.5876",
    "ILD": "0.9023",
    "GAS": "0.8016",
}
TOLERANCE = D("0.00005")

pytestmark = [
    pytest.mark.django_db,
    pytest.mark.skipif(not (FIXTURES / "most_fy2023_gas.json").exists(), reason="P4.2 fixtures missing"),
]


def test_most_figures_through_the_application():
    agency = make_agency("most")
    root = make_root(agency)
    rds = make_office(root, "RDS")
    offices = {code: make_office(rds if code in ("RDI", "AST", "ILD") else root, code) for code in EXPECTED}
    assign(make_user(agency, "boss@most.gov"), root, "admin")
    api = Json(api_client("boss@most.gov"))
    fy = api.post("/api/v1/fiscal-years", {"label": "2023", "start_year": 2023}).json()
    api.patch(f"/api/v1/fiscal-years/{fy['id']}", {"status": "open"})
    periods = {
        p["month_index"]: p["id"] for p in api.get(f"/api/v1/fiscal-years/{fy['id']}").json()["periods"]
    }
    rows_by_office = fixture_plans()

    for code, rows in rows_by_office.items():
        office = offices[code]
        plan = api.post("/api/v1/plans", {"office_id": str(office.id), "fiscal_year_id": fy["id"]}).json()
        saved = api.post(f"/api/v1/plans/{plan['id']}/save", {"rows": rows})
        assert saved.status_code == 200, saved.content
        lineage = {r["code"]: r["lineage_id"] for r in saved.json()["plan"]["rows"]}
        assert api.post(f"/api/v1/plans/{plan['id']}/submit").status_code == 200
        assert api.post(f"/api/v1/plans/{plan['id']}/approve").status_code == 200
        data = json.loads((FIXTURES / f"most_fy2023_{code.lower()}.json").read_text())
        for month in range(1, 13):
            acts = [
                {"lineage_id": lineage[f"{code}-{i}"], "actual": a["actual"][month - 1]}
                for i, a in enumerate(data["activities"], start=1)
            ]
            r = api.post(
                "/api/v1/reports/save",
                {"office": str(office.id), "period": periods[month], "activities": acts},
            )
            assert r.status_code == 200, r.content

    with context.agency_context(agency.id):
        got = {}
        for code in EXPECTED:
            plan = Plan.objects.get(office=offices[code], status="approved")
            got[code] = results.live_plan_result(plan)
        for code, expected in EXPECTED.items():
            assert abs(got[code].cum_actual[11] - D(expected)) <= TOLERANCE, (code, got[code].cum_actual[11])
        rds_result = engine.rollup(
            [got["RDI"], got["AST"], got["ILD"]], Plan.objects.first().fiscal_year.profile.to_engine()
        )
        assert abs(rds_result.cum_actual[11] - D("0.8619")) <= TOLERANCE
        assert got["GAS"].funds_total == D("107678522")

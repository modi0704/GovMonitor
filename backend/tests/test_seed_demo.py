from pathlib import Path

import pytest
from django.core.management import call_command

from apps.accounts.models import User
from apps.structure.models import Office, OfficeGroup, OrgLevel
from apps.tenancy.models import Agency


@pytest.mark.django_db(databases=["default", "owner"], transaction=True)
def test_seed_demo_is_idempotent_and_builds_three_and_five_level_agencies():
    call_command("seed_demo")
    counts = Office.objects.using("owner").count()
    call_command("seed_demo")
    assert Office.objects.using("owner").count() == counts
    agencies = {a.code: a for a in Agency.objects.using("owner").all()}
    assert set(agencies) == {"sample-ministry", "sample-bureau"}
    assert User.objects.using("owner").count() == 2

    def depth(code):
        offices = Office.objects.using("owner").filter(agency=agencies[code])
        return max(o.depth for o in offices) + 1, OrgLevel.objects.using("owner").filter(
            agency=agencies[code]
        ).count()

    assert depth("sample-ministry") == (3, 3)
    assert depth("sample-bureau") == (5, 5)
    groups = OfficeGroup.objects.using("owner").filter(agency=agencies["sample-ministry"])
    assert {g.name: g.members.count() for g in groups} == {"Mainland centers": 4, "Island centers": 3}
    # Phase 5 exit: the six MOST sheets (P4.2 fixtures) are approved plans, loaded through the API
    # (so audited). Without the fixtures the seed falls back to the 8.1 worked example for PME.
    from apps.audit.models import AuditLog
    from apps.planning.models import Plan

    plans = Plan.objects.using("owner").filter(agency=agencies["sample-ministry"])
    counts = {p.office.code: (p.status, p.rows.filter(row_kind="activity").count()) for p in plans}
    if (Path(__file__).resolve().parents[1] / "fixtures" / "most_fy2023_rdi.json").exists():
        assert counts == {
            "PME": ("approved", 6),
            "HRM": ("approved", 9),
            "RDI": ("approved", 10),
            "AST": ("approved", 6),
            "ILD": ("approved", 31),
            "GAS": ("approved", 1),
        }
    else:
        assert counts == {"PME": ("approved", 3)}
    if "RDI" in counts:
        # Phase 8 exit: December locked; the dashboard shows the MOST December 2023 figures.
        from apps.planning.models import ReportingPeriod
        from apps.results.models import PeriodResult

        dec = ReportingPeriod.objects.using("owner").get(
            fiscal_year__agency=agencies["sample-ministry"], month_index=12
        )
        assert dec.status == "locked"
        frozen = {
            r.office.code: round(float(r.cum_actual) * 100, 2)
            for r in PeriodResult.objects.using("owner")
            .select_related("office")
            .filter(period=dec, view="owner")
        }
        frozen_expected = {
            "PME": 95.83,
            "HRM": 83.68,
            "RDI": 99.07,
            "AST": 58.76,
            "ILD": 90.23,
            "GAS": 80.16,
            "RDS": 86.19,
        }
        assert {k: frozen[k] for k in frozen_expected} == frozen_expected
        assert Office.objects.using("owner").filter(agency=agencies["sample-ministry"], code="RDS").exists()
    if "RDI" in counts:
        # ...and the dashboard API shows them (Phase 8 exit check).
        from django.test import Client

        web = Client()
        web.post(
            "/api/v1/auth/login",
            {"email": "admin@sample-ministry.demo", "password": "demo-password-2026"},
            content_type="application/json",
        )
        codes = {o["code"]: o["id"] for o in web.get("/api/v1/offices").json()}
        shown = {}
        for code in ("PME", "HRM", "RDI", "AST", "ILD", "GAS", "RDS"):
            d = web.get("/api/v1/dashboard", {"office": codes[code], "period": str(dec.pk)}).json()
            assert d["label"] == "FINAL"
            shown[code] = round(float(d["headline"]["cum_actual"]) * 100, 2)
        assert shown == frozen_expected
    actions = set(
        AuditLog.objects.using("owner")
        .filter(agency=agencies["sample-ministry"])
        .values_list("action", flat=True)
    )
    assert {"submit", "approve"} <= actions
    # every path is consistent with its parent chain
    for office in Office.objects.using("owner").select_related("parent"):
        expected = f"/{office.pk}/" if office.parent_id is None else f"{office.parent.path}{office.pk}/"
        assert office.path == expected


@pytest.mark.django_db(databases=["default", "owner"], transaction=True)
def test_sample_bureau_is_a_different_shape_entered_through_the_api():
    """P14.4: the second demo agency proves nothing is hard-coded — five levels, the capped preset
    with equal weighting, plans at the lowest level, two locked months and an open one."""
    from django.test import Client

    from apps.planning.models import Plan, ReportingPeriod, ScoringProfile
    from apps.results.models import PeriodResult

    call_command("seed_demo")
    call_command("seed_demo")  # idempotent
    bureau = Agency.objects.using("owner").get(code="sample-bureau")
    profile = ScoringProfile.objects.using("owner").get(fiscal_year__agency=bureau, fiscal_year__label="2026")
    assert (profile.weighting, profile.cap_at_100) == ("equal", True)
    plans = Plan.objects.using("owner").filter(agency=bureau, status="approved")
    assert sorted(p.office.code for p in plans) == [
        "R1-P1-D1-U1",
        "R1-P1-D1-U2",
        "R1-P1-D2-U1",
        "R2-P1-D1-U1",
    ]
    assert all(p.office.depth == 4 for p in plans)  # plans live at the fifth level
    statuses = dict(
        ReportingPeriod.objects.using("owner")
        .filter(fiscal_year__agency=bureau, month_index__lte=3)
        .values_list("month_index", "status")
    )
    assert statuses == {1: "locked", 2: "locked", 3: "open"}
    feb_root = PeriodResult.objects.using("owner").get(
        agency=bureau, period__month_index=2, office__code="BUR", view="owner"
    )
    assert feb_root.profile_snapshot["weighting"] == "equal"

    web = Client()
    web.post("/api/v1/auth/login", {"email": "admin@sample-bureau.demo", "password": "demo-password-2026"},
             content_type="application/json")  # fmt: skip
    root = next(o for o in web.get("/api/v1/offices").json() if o["code"] == "BUR")
    march = ReportingPeriod.objects.using("owner").get(fiscal_year__agency=bureau, month_index=3)
    d = web.get("/api/v1/dashboard", {"office": root["id"], "period": str(march.pk)}).json()
    assert d["label"] == "PROVISIONAL" and d["has_result"]
    # Equal weighting: every activity of a unit weighs a quarter, whatever it costs.
    unit = next(o for o in web.get("/api/v1/offices").json() if o["code"] == "R1-P1-D1-U1")
    acts = web.get("/api/v1/dashboard/activities", {"office": unit["id"], "period": str(march.pk)}).json()
    assert {a["weight"] for a in acts["activities"]} == {"0.25"}

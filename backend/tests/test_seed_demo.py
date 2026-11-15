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

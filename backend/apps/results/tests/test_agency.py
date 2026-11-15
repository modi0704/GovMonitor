"""P7.1: compute_agency — owner roll-up, implementing view, sibling and group ranks."""

from decimal import Decimal as D

import pytest

from apps.planning.models import ReportingPeriod
from apps.results.agency import IMPLEMENTING, OWNER, compute_agency, compute_live
from apps.structure.models import OfficeGroup, OfficeGroupMember
from apps.tenancy import context
from tests.reporting_helpers import client, reporting_world

pytestmark = pytest.mark.django_db


def r6(v):
    return round(float(v), 6)


@pytest.fixture
def w():
    w = reporting_world()
    div = client(w, "div")
    base = {"office": str(w["div"].id)}
    for month, acts in {1: {"A": "2"}, 2: {"A": "2", "B": "1"}, 3: {"A": "4", "B": "3"}}.items():
        div.post(
            "/api/v1/reports/save",
            {
                **base,
                "period": w["periods"][month]["id"],
                "activities": [
                    {"lineage_id": w["acts"][k]["lineage_id"], "actual": v} for k, v in acts.items()
                ],
            },
        )
    return w


def test_owner_rollup_implementing_view_and_ranks(w):
    with context.agency_context(w["agency"].id):
        march = ReportingPeriod.objects.get(pk=w["periods"][3]["id"])
        agency = compute_agency(march)
        div = agency.get(w["div"].id)
        assert (r6(div.result.cum_plan[2]), r6(div.result.cum_actual[2])) == (1.0, 0.78)  # 8.1 March
        assert div.plan_version == 1 and len(div.activity_rows) == 3
        # The root has no plan of its own: its result is the roll-up of its children (only DIV has one).
        root = agency.get(w["root"].id)
        assert root.plan_version is None and r6(root.result.cum_actual[2]) == 0.78
        assert agency.get(w["other"].id).result is None  # no approved plan
        # UNIT owns nothing (no owner result) but implements A: 2+2+4 = 8 of 10 by March.
        assert agency.get(w["unit"].id).result is None
        unit_impl = agency.get(w["unit"].id, IMPLEMENTING)
        assert r6(unit_impl.result.cum_actual[2]) == 0.8 and [a.code for a, _ in unit_impl.activity_rows] == [
            "A"
        ]
        # Siblings under the root: DIV ranked, OTHER listed last without a rank.
        assert (div.rank_sibling, agency.get(w["other"].id).rank_sibling) == (1, None)
        live = compute_live(march, w["div"], OWNER)
        assert r6(live.result.cum_actual[2]) == 0.78


def test_group_members_without_a_plan_use_the_implementing_view(w):
    with context.agency_context(w["agency"].id):
        group = OfficeGroup.objects.create(name="Field")
        for o in (w["div"], w["unit"], w["other"]):
            OfficeGroupMember.objects.create(group=group, office=o)
        jan = ReportingPeriod.objects.get(pk=w["periods"][1]["id"])
        agency = compute_agency(jan)
        rows = {r.office_id: r for r in agency.group_rankings[group.id]}
        # January: DIV 0.12 (owner view); UNIT 0.2 (implementing view: A alone); OTHER nothing.
        assert r6(rows[str(w["unit"].id)].value) == 0.2 and rows[str(w["unit"].id)].rank == 1
        assert r6(rows[str(w["div"].id)].value) == 0.12 and rows[str(w["div"].id)].rank == 2
        assert rows[str(w["other"].id)].rank is None
        assert agency.get(w["div"].id).group_ranks == {str(group.id): 2}
        assert D(0) == agency.get(w["root"].id).result.variance[0]

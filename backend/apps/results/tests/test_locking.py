"""P7.3 lock and P7.4 unlock."""

import pytest

from apps.audit.models import AuditLog
from apps.reporting.models import OfficeSubmission
from apps.results.models import PeriodResult
from apps.tenancy import context
from tests.reporting_helpers import client, reporting_world

pytestmark = pytest.mark.django_db


@pytest.fixture
def w():
    w = reporting_world()
    div = client(w, "div")
    for month, acts in {1: {"A": "2"}, 2: {"A": "2", "B": "1"}}.items():
        div.post(
            "/api/v1/reports/save",
            {
                "office": str(w["div"].id),
                "period": w["periods"][month]["id"],
                "activities": [
                    {"lineage_id": w["acts"][k]["lineage_id"], "actual": v} for k, v in acts.items()
                ],
            },
        )
    return w


def lock(c, w, m):
    return c.post(f"/api/v1/periods/{w['periods'][m]['id']}/lock")


def unlock(c, w, m, reason="Correction"):
    return c.post(f"/api/v1/periods/{w['periods'][m]['id']}/unlock", {"reason": reason})


def rows(w, m):
    with context.agency_context(w["agency"].id):
        return {
            (str(r.office_id), r.view): r
            for r in PeriodResult.objects.filter(period_id=w["periods"][m]["id"])
        }


def test_lock_freezes_results_and_submissions_in_order(w):
    boss = client(w, "boss")
    assert lock(client(w, "div"), w, 1).status_code == 403
    r = lock(boss, w, 2)
    assert r.status_code == 409 and r.json()["code"] == "earlier_open"
    assert lock(boss, w, 1).json()["status"] == "locked"
    assert lock(boss, w, 1).json()["code"] == "already_locked"
    frozen = rows(w, 1)
    div = frozen[(str(w["div"].id), "owner")]
    assert (float(div.cum_actual), float(div.cum_plan), div.status_label) == (0.12, 0.12, "ON-TIME")
    assert (
        div.plan_version == 1
        and div.rank_sibling == 1
        and div.profile_snapshot["preset"] == "workbook_compatible"
    )
    assert [a["code"] for a in div.detail["activities"]] == ["A", "B", "C"]
    assert len(div.detail["series"]["cum_actual"]) == 12
    assert (str(w["root"].id), "owner") in frozen  # roll-up of the root
    assert float(frozen[(str(w["unit"].id), "implementing")].cum_actual) == 0.2
    with context.agency_context(w["agency"].id):
        assert set(
            OfficeSubmission.objects.filter(period_id=w["periods"][1]["id"]).values_list("status", flat=True)
        ) == {"locked"}
    # Nothing can be saved in a locked month.
    r = client(w, "div").post(
        "/api/v1/reports/save",
        {
            "office": str(w["div"].id),
            "period": w["periods"][1]["id"],
            "activities": [{"lineage_id": w["acts"]["A"]["lineage_id"], "actual": "9"}],
        },
    )
    assert r.status_code == 409


def test_unlock_latest_only_with_reason_and_relock_recomputes(w):
    boss = client(w, "boss")
    lock(boss, w, 1)
    lock(boss, w, 2)
    assert unlock(boss, w, 1).json()["code"] == "later_locked"
    assert unlock(boss, w, 2, reason=" ").status_code == 400
    assert unlock(boss, w, 2).json() == {"status": "open", "results_removed": len(rows(w, 1))}
    assert rows(w, 2) == {}
    with context.agency_context(w["agency"].id):
        entry = AuditLog.objects.filter(action="unlock").latest("id")
    assert entry.after["reason"] == "Correction"
    assert {(r["office_code"], r["view"]) for r in entry.before["results"]} >= {
        ("DIV", "owner"),
        ("UNIT", "implementing"),
    }
    # Correct February and lock again: the frozen result is recomputed.
    client(w, "div").post(
        "/api/v1/reports/save",
        {
            "office": str(w["div"].id),
            "period": w["periods"][2]["id"],
            "activities": [{"lineage_id": w["acts"]["B"]["lineage_id"], "actual": "2"}],
        },
    )
    lock(boss, w, 2)
    assert float(rows(w, 2)[(str(w["div"].id), "owner")].cum_actual) == 0.39  # 0.6·0.4 + 0.3·0.5
    with context.agency_context(w["agency"].id):
        actions = list(
            AuditLog.objects.filter(action__in=["lock", "unlock"])
            .order_by("id")
            .values_list("action", flat=True)
        )
    assert actions == ["lock", "lock", "unlock", "lock"]

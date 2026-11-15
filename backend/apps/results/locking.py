"""Locking and unlocking a month (MASTERPLAN D4, P7.3, P7.4).

Lock: in one transaction, the period becomes ``locked``, every submission of the month becomes
``locked`` and a ``period_result`` row is written for every office and view, with a copy of the
scoring profile. Allowed only when every earlier month of the year is locked.

Unlock: agency administrator only, with a reason, and only for the latest locked month. The frozen
rows are copied into the audit record, then deleted; locking again recomputes them.
"""

from decimal import Decimal

from django.db import transaction
from django.utils import timezone

from apps.audit import services as audit
from apps.audit.services import jsonable
from apps.planning.models import Plan, ReportingPeriod
from apps.planning.numbers import plain
from apps.reporting.models import OfficeSubmission
from apps.results.agency import compute_agency
from apps.results.models import PeriodResult

RATIO_PLACES = Decimal("1e-10")
MONEY_PLACES = Decimal("0.01")


class LockError(Exception):
    def __init__(self, code: str, message: str, http: int = 409):
        super().__init__(message)
        self.code = code
        self.message = message
        self.http = http


def _ratio(v):
    return None if v is None else Decimal(v).quantize(RATIO_PLACES)


def _money(v):
    return None if v is None else Decimal(v).quantize(MONEY_PLACES)


def _detail(entry, month: int, profile=None) -> dict:
    """Per-activity and per-indicator figures for one month, as stored in a frozen row (6.4)."""
    from apps.scoring import engine

    i = month - 1
    activities = []
    for row, res in entry.activity_rows:
        planned = entry.planned.get(row.id) if entry.planned else None
        if planned is None:
            planned = {t.period.month_index: t.planned_qty for t in row.targets.all()}
        reported = entry.actuals.get(row.lineage_id, {})
        this = reported.get(month)
        variance = res.actual_ratio[i] - res.planned_ratio[i]
        activities.append(
            {
                "lineage_id": str(row.lineage_id),
                "code": row.code,
                "title": row.title,
                "unit": row.unit,
                "owner_office_id": str(row.plan.office_id),
                "implementing_office_id": str(row.implementing_office_id or row.plan.office_id),
                "annual_target": plain(row.annual_target),
                "weight": jsonable(res.weight),
                "planned_ratio": jsonable(res.planned_ratio[i]),
                "actual_ratio": jsonable(res.actual_ratio[i]),
                "variance": jsonable(variance),
                "status_kind": "no_target"
                if res.no_target
                else (engine.status_kind(variance, profile) if profile else None),
                "cum_target": plain(
                    sum((planned.get(m, Decimal(0)) for m in range(1, month + 1)), Decimal(0))
                ),
                "cum_actual": plain(
                    sum((a.actual_qty for m, a in reported.items() if m <= month), Decimal(0))
                ),
                "month_target": plain(planned.get(month, Decimal(0))),
                "month_actual": plain(this.actual_qty) if this else None,
                "delay_reason": this.delay_reason if this else "",
                "remarks": this.remarks if this else "",
                "no_target": res.no_target,
            }
        )
    indicators = []
    for ind, res in entry.indicator_rows:
        reported = {
            m: a.actual_value
            for m, a in entry.indicator_actuals.get(ind.lineage_id, {}).items()
            if m <= month
        }
        values = [v for m, v in sorted(reported.items()) if v is not None]
        to_date = (values[-1] if values else None) if ind.aggregation == "last" else sum(values, Decimal(0))
        indicators.append(
            {
                "lineage_id": str(ind.lineage_id),
                "code": ind.code,
                "name": ind.name,
                "unit": ind.unit,
                "annual_target": plain(ind.annual_target),
                "actual_to_date": plain(to_date),
                "rate": jsonable(res.rate[i]),
            }
        )
    result = entry.result
    return {
        "activities": activities,
        "indicators": indicators,
        "group_ranks": entry.group_ranks,
        "series": {
            "cum_plan": [jsonable(v) for v in result.cum_plan],
            "cum_actual": [jsonable(v) for v in result.cum_actual],
        },
    }


@transaction.atomic
def lock_period(period: ReportingPeriod, user) -> int:
    period = (
        ReportingPeriod.objects.select_for_update(of=("self",))
        .select_related("fiscal_year__profile")
        .get(pk=period.pk)
    )
    if period.status == ReportingPeriod.Status.LOCKED:
        raise LockError("already_locked", "This month is already locked.")
    earlier_open = ReportingPeriod.objects.filter(
        fiscal_year=period.fiscal_year, month_index__lt=period.month_index, status=ReportingPeriod.Status.OPEN
    ).order_by("month_index")
    if earlier_open.exists():
        first = earlier_open.first()
        raise LockError("earlier_open", f"Lock {first.start_date:%B %Y} first: months are locked in order.")

    month = period.month_index
    agency = compute_agency(period)
    snapshot = period.fiscal_year.profile.snapshot()
    rows = []
    for (office_id, view), entry in agency.entries.items():
        if entry.result is None:
            continue
        at = entry.result.at(month)
        rows.append(
            PeriodResult(
                period=period,
                office_id=office_id,
                view=view,
                plan_version=entry.plan_version,
                periodic_plan=_ratio(at["periodic_plan"]),
                periodic_actual=_ratio(at["periodic_actual"]),
                cum_plan=_ratio(at["cum_plan"]),
                cum_actual=_ratio(at["cum_actual"]),
                variance=_ratio(at["variance"]),
                status_label=at["status"],
                funds_total=_money(at["funds_total"]),
                funds_used_est=_money(at["funds_used_est"]),
                funds_used_actual=_money(at["funds_used_actual"]),
                indicator_score=_ratio(at["indicator_score"]),
                rank_sibling=entry.rank_sibling if view == "owner" else None,
                detail=_detail(entry, month, agency.profile),
                profile_snapshot=snapshot,
            )
        )
    with audit.suppressed():  # one "lock" event below, not one per row
        PeriodResult.objects.bulk_create(rows)
        planned_offices = set(
            Plan.objects.filter(fiscal_year=period.fiscal_year, status=Plan.Status.APPROVED).values_list(
                "office_id", flat=True
            )
        )
        existing = set(OfficeSubmission.objects.filter(period=period).values_list("office_id", flat=True))
        OfficeSubmission.objects.bulk_create(
            [OfficeSubmission(office_id=o, period=period) for o in planned_offices - existing]
        )
        OfficeSubmission.objects.filter(period=period).update(status=OfficeSubmission.Status.LOCKED)
        period.status = ReportingPeriod.Status.LOCKED
        period.locked_by = user
        period.locked_at = timezone.now()
        period.save(update_fields=["status", "locked_by", "locked_at"])
    audit.record(
        "lock",
        period,
        after={"month": month, "results": len(rows), "profile_version": snapshot["version"]},
    )
    from apps.alerts import services as alerts

    alerts.period_locked(period)
    return len(rows)


@transaction.atomic
def unlock_period(period: ReportingPeriod, user, reason: str) -> int:
    reason = (reason or "").strip()
    if not reason:
        raise LockError(
            "reason_required", "Give the reason for unlocking; it is kept in the audit log.", http=400
        )
    period = ReportingPeriod.objects.select_for_update(of=("self",)).get(pk=period.pk)
    if period.status != ReportingPeriod.Status.LOCKED:
        raise LockError("not_locked", "This month is not locked.")
    if ReportingPeriod.objects.filter(
        fiscal_year=period.fiscal_year,
        month_index__gt=period.month_index,
        status=ReportingPeriod.Status.LOCKED,
    ).exists():
        raise LockError("later_locked", "Only the latest locked month can be unlocked.")
    frozen = list(PeriodResult.objects.filter(period=period).select_related("office"))
    copy = [
        {
            "office_id": str(r.office_id),
            "office_code": r.office.code,
            "view": r.view,
            "plan_version": r.plan_version,
            "cum_plan": jsonable(r.cum_plan),
            "cum_actual": jsonable(r.cum_actual),
            "variance": jsonable(r.variance),
            "status_label": r.status_label,
            "funds_total": jsonable(r.funds_total),
            "funds_used_est": jsonable(r.funds_used_est),
            "funds_used_actual": jsonable(r.funds_used_actual),
            "indicator_score": jsonable(r.indicator_score),
            "rank_sibling": r.rank_sibling,
            "profile_version": r.profile_snapshot.get("version"),
            "computed_at": r.computed_at.isoformat(),
        }
        for r in frozen
    ]
    with audit.suppressed():
        PeriodResult.objects.filter(period=period).delete()
        for sub in OfficeSubmission.objects.filter(period=period, status=OfficeSubmission.Status.LOCKED):
            sub.status = (
                OfficeSubmission.Status.SUBMITTED if sub.submitted_at else OfficeSubmission.Status.DRAFT
            )
            sub.save(update_fields=["status"])
        period.status = ReportingPeriod.Status.OPEN
        period.locked_by = None
        period.locked_at = None
        period.save(update_fields=["status", "locked_by", "locked_at"])
    audit.record(
        "unlock", period, before={"results": copy}, after={"month": period.month_index, "reason": reason}
    )
    from apps.alerts import services as alerts

    alerts.period_locked(period, unlocked=True, reason=reason)
    return len(copy)

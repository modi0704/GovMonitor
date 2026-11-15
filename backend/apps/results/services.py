"""Live results: load plans and actuals, call the scoring engine (MASTERPLAN 7.9, P6.3, P7.1).

Open periods are computed live from the currently approved plan version. Actuals are keyed by
lineage, so a revised plan keeps the accomplishments already reported; rows removed in the new
version are simply not loaded, so they stop being scored.
"""

from collections import defaultdict
from decimal import Decimal

from apps.planning.models import Activity, FiscalYear, Indicator, Plan
from apps.reporting.models import ActivityActual, IndicatorActual
from apps.scoring import engine
from apps.scoring.types import ActivityInput, IndicatorInput, OfficeResult

MONTHS = 12


def _series(values: dict, default=Decimal(0)) -> tuple:
    return tuple(values.get(m, default) for m in range(1, MONTHS + 1))


def load_activity_actuals(fiscal_year: FiscalYear, lineages) -> dict:
    """lineage -> {month_index: ActivityActual}"""
    out: dict = defaultdict(dict)
    rows = ActivityActual.objects.select_related("period").filter(
        period__fiscal_year=fiscal_year, activity_lineage_id__in=list(lineages)
    )
    for a in rows:
        out[a.activity_lineage_id][a.period.month_index] = a
    return out


def load_indicator_actuals(fiscal_year: FiscalYear, lineages) -> dict:
    out: dict = defaultdict(dict)
    rows = IndicatorActual.objects.select_related("period").filter(
        period__fiscal_year=fiscal_year, indicator_lineage_id__in=list(lineages)
    )
    for a in rows:
        out[a.indicator_lineage_id][a.period.month_index] = a
    return out


def activity_input(row: Activity, actuals: dict, overrides: dict | None = None) -> ActivityInput:
    """``overrides``: {(lineage, month): (qty, amount)} for unsaved values typed in the browser."""
    planned = {t.period.month_index: t.planned_qty for t in row.targets.all()}
    reported = actuals.get(row.lineage_id, {})
    qty, amount = {}, {}
    for month, a in reported.items():
        qty[month] = a.actual_qty
        amount[month] = a.actual_amount
    for (lineage, month), (q, amt) in (overrides or {}).items():
        if lineage == row.lineage_id:
            qty[month] = q
            amount[month] = amt
    return ActivityInput(
        id=str(row.lineage_id),
        measure_type=row.measure_type or "quantity",
        annual_target=row.annual_target or Decimal(0),
        total_cost=row.total_cost or Decimal(0),
        planned=_series(planned),
        actual=_series(qty, None),
        actual_amount=_series(amount, None),
        manual_weight=row.manual_weight,
        implementing_office_id=str(row.implementing_office_id or ""),
        title=row.title,
    )


def indicator_input(ind: Indicator, actuals: dict, overrides: dict | None = None) -> IndicatorInput:
    planned = {t.period.month_index: t.planned_value for t in ind.targets.all()}
    values = {m: a.actual_value for m, a in actuals.get(ind.lineage_id, {}).items()}
    for (lineage, month), v in (overrides or {}).items():
        if lineage == ind.lineage_id:
            values[month] = v
    return IndicatorInput(
        id=str(ind.lineage_id),
        annual_target=ind.annual_target,
        actual=_series(values, None),
        planned=_series(planned),
        weight=ind.weight,
        aggregation=ind.aggregation,
        name=ind.name,
    )


def plan_activities(plan: Plan):
    return list(
        plan.rows.filter(row_kind=Activity.RowKind.ACTIVITY)
        .select_related("implementing_office")
        .prefetch_related("targets__period")
        .order_by("sort_order")
    )


def live_plan_result(
    plan: Plan, overrides: dict | None = None, indicator_overrides: dict | None = None
) -> OfficeResult:
    """Owner view of one approved plan, all 12 months, from the reported actuals (plus overrides)."""
    rows = plan_activities(plan)
    actuals = load_activity_actuals(plan.fiscal_year, [r.lineage_id for r in rows])
    inds = list(plan.indicators.prefetch_related("targets__period").order_by("sort_order"))
    ind_actuals = load_indicator_actuals(plan.fiscal_year, [i.lineage_id for i in inds])
    return engine.plan_result(
        [activity_input(r, actuals, overrides) for r in rows],
        [indicator_input(i, ind_actuals, indicator_overrides) for i in inds],
        plan.fiscal_year.profile.to_engine(),
    )


def implementing_activities(office, fiscal_year: FiscalYear):
    """Every activity of any approved plan of the year carried out by ``office`` (7.7)."""
    return list(
        Activity.objects.filter(
            row_kind=Activity.RowKind.ACTIVITY,
            implementing_office=office,
            plan__fiscal_year=fiscal_year,
            plan__status=Plan.Status.APPROVED,
        )
        .select_related("plan__office", "implementing_office")
        .prefetch_related("targets__period")
        .order_by("plan__office__path", "sort_order")
    )


def live_implementing_result(
    office, fiscal_year: FiscalYear, overrides: dict | None = None
) -> OfficeResult | None:
    rows = implementing_activities(office, fiscal_year)
    if not rows:
        return None
    actuals = load_activity_actuals(fiscal_year, [r.lineage_id for r in rows])
    return engine.implementing_result(
        [activity_input(r, actuals, overrides) for r in rows], fiscal_year.profile.to_engine()
    )


def headline(result: OfficeResult | None, month: int, profile=None) -> dict | None:
    """One month's figures; with ``profile`` (engine Profile) also the status kind for colouring."""
    if result is None:
        return None
    from apps.audit.services import jsonable

    data = jsonable(result.at(month))
    if profile is not None:
        data["status_kind"] = engine.status_kind(result.variance[month - 1], profile)
    return data

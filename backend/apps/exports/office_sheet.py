"""Everything one office sheet of the Excel export shows, loaded once (MASTERPLAN 9.1, P9.2).

The plan is the version that was scored for the month: the frozen ``period_result.plan_version``
for a locked month, the approved plan for an open one. Actuals stop at the selected month. The
engine values written where a formula cannot reproduce the result (recurring measures,
non-default profiles) come from ``apps.scoring`` with exactly these inputs.
"""

from dataclasses import dataclass, field
from decimal import Decimal

from apps.planning.models import Activity, ActivityTarget, Indicator, IndicatorTarget, Plan, ReportingPeriod
from apps.results.agency import OWNER
from apps.results.models import PeriodResult
from apps.results.read import period_profile
from apps.scoring import engine
from apps.scoring.presets import DEFAULT_PRESET
from apps.scoring.types import ActivityInput, IndicatorInput, OfficeResult

MONTHS = 12


@dataclass
class ActivityLine:
    row: Activity
    planned: list  # 12 planned quantities (Decimal; 0 when none)
    actual: list  # 12 actual quantities (Decimal | None); None after the selected month
    input: ActivityInput | None = None


@dataclass
class IndicatorLine:
    indicator: Indicator
    targets: list  # 12 monthly targets
    actual: list  # 12 actuals (Decimal | None)
    weight: Decimal = Decimal(0)


@dataclass
class OfficeSheet:
    office: object
    plan: Plan
    month: int
    month_starts: list  # the start date of each of the 12 months, fiscal-year order
    rows: list  # outline rows (Activity) and ActivityLine, in plan order
    indicators: list  # IndicatorLine
    result: OfficeResult
    profile: object  # engine Profile
    activity_results: dict = field(default_factory=dict)  # lineage (str) -> ActivityResult

    @property
    def formulas_reproduce_engine(self) -> bool:
        return formulas_reproduce(self.profile)

    @property
    def status(self) -> str:
        return self.result.status[self.month - 1]


def formulas_reproduce(profile) -> bool:
    """``=O*M/I`` and ``=L/$L$t`` give the engine's numbers only under the default preset's cost-share
    weights without the 100% cap; any other profile gets engine values in the total rows (9.1)."""
    return profile.preset == DEFAULT_PRESET and profile.weighting == "cost_share" and not profile.cap_at_100


def plan_for(office, period: ReportingPeriod) -> Plan | None:
    fy = period.fiscal_year
    if period.status == ReportingPeriod.Status.LOCKED:
        version = (
            PeriodResult.objects.filter(period=period, office=office, view=OWNER)
            .values_list("plan_version", flat=True)
            .first()
        )
        if version is None:
            return None
        return Plan.objects.filter(office=office, fiscal_year=fy, version=version).first()
    return Plan.objects.filter(office=office, fiscal_year=fy, status=Plan.Status.APPROVED).first()


def _months(values: dict, default) -> list:
    return [values.get(m, default) for m in range(1, MONTHS + 1)]


def load(
    office, period: ReportingPeriod, actuals: dict, ind_actuals: dict, profile=None
) -> OfficeSheet | None:
    """``actuals`` / ``ind_actuals``: the year's actuals from ``results.services.load_*_actuals``."""
    plan = plan_for(office, period)
    if plan is None:
        return None
    month = period.month_index
    profile = profile or period_profile(period)
    rows = list(plan.rows.select_related("implementing_office").order_by("sort_order"))
    acts = [r for r in rows if r.row_kind == Activity.RowKind.ACTIVITY]
    planned: dict = {}
    for activity_id, m, qty in ActivityTarget.objects.filter(activity__in=acts).values_list(
        "activity_id", "period__month_index", "planned_qty"
    ):
        planned.setdefault(activity_id, {})[m] = qty

    lines, out_rows = {}, []
    for r in rows:
        if r.row_kind != Activity.RowKind.ACTIVITY:
            out_rows.append(r)
            continue
        reported = {m: a.actual_qty for m, a in actuals.get(r.lineage_id, {}).items() if m <= month}
        amounts = {m: a.actual_amount for m, a in actuals.get(r.lineage_id, {}).items() if m <= month}
        line = ActivityLine(r, _months(planned.get(r.id, {}), Decimal(0)), _months(reported, None))
        line.input = ActivityInput(
            id=str(r.lineage_id),
            measure_type=r.measure_type or "quantity",
            annual_target=r.annual_target or Decimal(0),
            total_cost=r.total_cost or Decimal(0),
            planned=tuple(line.planned),
            actual=tuple(line.actual),
            actual_amount=tuple(_months(amounts, None)),
            manual_weight=r.manual_weight,
            title=r.title,
        )
        lines[r.id] = line
        out_rows.append(line)

    inds = list(plan.indicators.order_by("sort_order"))
    targets: dict = {}
    for ind_id, m, value in IndicatorTarget.objects.filter(indicator__in=inds).values_list(
        "indicator_id", "period__month_index", "planned_value"
    ):
        targets.setdefault(ind_id, {})[m] = value
    ind_lines, ind_inputs = [], []
    for i in inds:
        values = {m: a.actual_value for m, a in ind_actuals.get(i.lineage_id, {}).items() if m <= month}
        line = IndicatorLine(i, _months(targets.get(i.id, {}), Decimal(0)), _months(values, None))
        ind_lines.append(line)
        ind_inputs.append(
            IndicatorInput(
                id=str(i.lineage_id),
                annual_target=i.annual_target,
                actual=tuple(line.actual),
                planned=tuple(line.targets),
                weight=i.weight,
                aggregation=i.aggregation,
                name=i.name,
            )
        )

    result = engine.plan_result([lines[a.id].input for a in acts], ind_inputs, profile)
    for line, ind_result in zip(ind_lines, result.indicators, strict=True):
        line.weight = ind_result.weight
    starts = dict(period.fiscal_year.periods.values_list("month_index", "start_date"))
    return OfficeSheet(
        office=office,
        plan=plan,
        month=month,
        month_starts=[starts[m] for m in range(1, MONTHS + 1)],
        rows=out_rows,
        indicators=ind_lines,
        result=result,
        profile=profile,
        activity_results={a.id: a for a in result.activities},
    )

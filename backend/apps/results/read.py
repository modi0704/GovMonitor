"""The one results read path (MASTERPLAN 7.9, P7.8).

``get_result(period, office, view)`` returns the frozen ``period_result`` row for a locked month and
the live computation for an open one, flagged ``final`` / ``provisional``. Dashboards, rankings,
exports and alerts (Phases 8–11) read results only through this module.
"""

from dataclasses import dataclass, field
from decimal import Decimal

from apps.audit.services import jsonable
from apps.planning.models import ReportingPeriod
from apps.results.agency import IMPLEMENTING, OWNER, compute_agency
from apps.results.models import PeriodResult
from apps.scoring import engine, presets

ENGINE_KEYS = (
    "preset", "weighting", "cap_at_100", "on_time_tolerance", "label_ahead", "label_on_time", "label_delayed",
    "rollup", "indicator_weighting", "indicator_rollup", "ranking_metric",
)  # fmt: skip


@dataclass
class ResultView:
    office_id: str
    view: str
    month: int
    final: bool
    cum_plan: Decimal
    cum_actual: Decimal
    periodic_plan: Decimal
    periodic_actual: Decimal
    variance: Decimal
    status_label: str
    status_kind: str
    funds_total: Decimal
    funds_used_est: Decimal
    funds_used_actual: Decimal | None
    indicator_score: Decimal | None
    rank_sibling: int | None
    plan_version: int | None
    group_ranks: dict = field(default_factory=dict)
    series: dict = field(default_factory=dict)  # cum_plan / cum_actual for months 1..12
    activities: list = field(default_factory=list)
    indicators: list = field(default_factory=list)
    profile: dict = field(default_factory=dict)

    @property
    def label(self) -> str:
        return "FINAL" if self.final else "PROVISIONAL"

    def payload(self) -> dict:
        data = {k: jsonable(v) for k, v in self.__dict__.items()}
        data["label"] = self.label
        return data


def _engine_profile(snapshot: dict):
    return presets.profile_from_settings({k: snapshot[k] for k in ENGINE_KEYS if k in snapshot})


def _from_row(row: PeriodResult, month: int) -> ResultView:
    profile = _engine_profile(row.profile_snapshot)
    return ResultView(
        office_id=str(row.office_id),
        view=row.view,
        month=month,
        final=True,
        cum_plan=row.cum_plan,
        cum_actual=row.cum_actual,
        periodic_plan=row.periodic_plan,
        periodic_actual=row.periodic_actual,
        variance=row.variance,
        status_label=row.status_label,
        status_kind=engine.status_kind(row.variance, profile),
        funds_total=row.funds_total,
        funds_used_est=row.funds_used_est,
        funds_used_actual=row.funds_used_actual,
        indicator_score=row.indicator_score,
        rank_sibling=row.rank_sibling,
        plan_version=row.plan_version,
        group_ranks=row.detail.get("group_ranks", {}),
        series=row.detail.get("series", {}),
        activities=row.detail.get("activities", []),
        indicators=row.detail.get("indicators", []),
        profile=row.profile_snapshot,
    )


def _from_entry(entry, month: int, profile, snapshot: dict) -> ResultView:
    from apps.results.locking import _detail  # same per-activity detail as a frozen row

    result = entry.result
    at = result.at(month)
    detail = _detail(entry, month, profile)
    return ResultView(
        office_id=str(entry.office.id),
        view=entry.view,
        month=month,
        final=False,
        cum_plan=at["cum_plan"],
        cum_actual=at["cum_actual"],
        periodic_plan=at["periodic_plan"],
        periodic_actual=at["periodic_actual"],
        variance=at["variance"],
        status_label=at["status"],
        status_kind=engine.status_kind(at["variance"], profile),
        funds_total=at["funds_total"],
        funds_used_est=at["funds_used_est"],
        funds_used_actual=at["funds_used_actual"],
        indicator_score=at["indicator_score"],
        rank_sibling=entry.rank_sibling if entry.view == OWNER else None,
        plan_version=entry.plan_version,
        group_ranks=entry.group_ranks,
        series=detail["series"],
        activities=detail["activities"],
        indicators=detail["indicators"],
        profile=snapshot,
    )


def get_agency_results(period: ReportingPeriod) -> dict:
    """(office id as str, view) -> ResultView, for every office with a result in this month."""
    month = period.month_index
    if period.status == ReportingPeriod.Status.LOCKED:
        rows = PeriodResult.objects.filter(period=period)
        return {(str(r.office_id), r.view): _from_row(r, month) for r in rows}
    agency = compute_agency(period)
    snapshot = period.fiscal_year.profile.snapshot()
    return {
        (str(office_id), view): _from_entry(entry, month, agency.profile, snapshot)
        for (office_id, view), entry in agency.entries.items()
        if entry.result is not None
    }


def get_result(period: ReportingPeriod, office, view: str = OWNER) -> ResultView | None:
    """One office's result for one month: frozen when the month is locked, live otherwise."""
    if view not in (OWNER, IMPLEMENTING):
        raise ValueError(f"unknown view {view!r}")
    office_id = getattr(office, "id", office)
    if period.status == ReportingPeriod.Status.LOCKED:
        row = PeriodResult.objects.filter(period=period, office_id=office_id, view=view).first()
        return _from_row(row, period.month_index) if row else None
    return get_agency_results(period).get((str(office_id), view))


def headline_of(rv: ResultView | None) -> dict | None:
    """The compact figures the monthly report and tiles show (same keys as the live headline)."""
    if rv is None:
        return None
    return jsonable(
        {
            "cum_plan": rv.cum_plan,
            "cum_actual": rv.cum_actual,
            "periodic_plan": rv.periodic_plan,
            "periodic_actual": rv.periodic_actual,
            "variance": rv.variance,
            "status": rv.status_label,
            "status_kind": rv.status_kind,
            "funds_total": rv.funds_total,
            "funds_used_est": rv.funds_used_est,
            "funds_used_actual": rv.funds_used_actual,
            "funds_remaining": rv.funds_total
            - (rv.funds_used_actual if rv.funds_used_actual is not None else rv.funds_used_est),
            "indicator_score": rv.indicator_score,
            "final": rv.final,
        }
    )


def period_profile(period: ReportingPeriod, results: dict | None = None):
    """The engine profile that judged this month: the locked snapshot, or today's settings."""
    if period.status == ReportingPeriod.Status.LOCKED:
        row = next(iter((results or {}).values()), None)
        if row is None:
            row_obj = PeriodResult.objects.filter(period=period).first()
            snapshot = row_obj.profile_snapshot if row_obj else period.fiscal_year.profile.snapshot()
        else:
            snapshot = row.profile
        return _engine_profile(snapshot)
    return period.fiscal_year.profile.to_engine()

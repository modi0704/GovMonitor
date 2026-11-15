"""Plain data classes for the scoring engine's input and output (MASTERPLAN 7, P4.1).

No ORM, no Django: ``results/services.py`` turns database rows into these, calls
``scoring.engine`` and stores or returns the output. All numbers are ``Decimal``; month series are
tuples of length 12 in fiscal-year order (index 0 = first month of the fiscal year).
"""

from dataclasses import dataclass, field
from decimal import Decimal

MONTHS = 12
ZERO = Decimal(0)
ONE = Decimal(1)

Series = tuple[Decimal, ...]
OptSeries = tuple[Decimal | None, ...]


def zeros() -> Series:
    return (ZERO,) * MONTHS


def nones() -> OptSeries:
    return (None,) * MONTHS


@dataclass(frozen=True)
class Profile:
    """The scoring settings of one fiscal year (6.4 scoring_profile)."""

    weighting: str = "cost_share"  # cost_share | equal | manual
    cap_at_100: bool = False
    on_time_tolerance: Decimal = ZERO
    label_ahead: str = "ADVANCED"
    label_on_time: str = "ON-TIME"
    label_delayed: str = "DELAYED"
    rollup: str = "budget_weighted"  # budget_weighted | simple_average
    indicator_weighting: str = "equal"  # equal | manual
    indicator_rollup: str = "all_indicators"  # all_indicators | office_scores
    ranking_metric: str = "cumulative_actual"  # cumulative_actual | variance | actual_over_plan
    preset: str = "workbook_compatible"


@dataclass(frozen=True)
class ActivityInput:
    """One scoreable plan line (row_kind = activity)."""

    id: str
    measure_type: str  # quantity | money | recurring
    annual_target: Decimal
    total_cost: Decimal
    planned: Series  # p_a,m: planned quantity (or amount) per month
    actual: OptSeries = field(default_factory=nones)  # x_a,m: reported per month (None = nothing reported)
    actual_amount: OptSeries = field(default_factory=nones)  # optional pesos spent per month (D7)
    manual_weight: Decimal | None = None
    implementing_office_id: str | None = None
    title: str = ""


@dataclass(frozen=True)
class IndicatorInput:
    id: str
    annual_target: Decimal
    actual: OptSeries = field(default_factory=nones)
    planned: Series = field(default_factory=zeros)
    weight: Decimal | None = None
    aggregation: str = "sum"  # sum | last
    name: str = ""


@dataclass(frozen=True)
class ActivityResult:
    id: str
    weight: Decimal
    planned_ratio: Series  # rp_a,m (cumulative)
    actual_ratio: Series  # ra_a,m (cumulative, capped if the profile says so)
    no_target: bool
    zero_cost: bool


@dataclass(frozen=True)
class IndicatorResult:
    id: str
    weight: Decimal
    rate: Series  # r_i,m


@dataclass(frozen=True)
class OfficeResult:
    """Result of one plan, one implementing set, or one rolled-up office, for all 12 months."""

    cum_plan: Series
    cum_actual: Series
    periodic_plan: Series
    periodic_actual: Series
    variance: Series
    status: tuple[str, ...]
    funds_total: Decimal
    funds_used_est: Series
    funds_used_actual: OptSeries
    funds_remaining: Series
    indicator_score: OptSeries  # None when there are no indicators
    # every indicator rate series in this result's subtree (for the all_indicators roll-up)
    indicator_rates: tuple[Series, ...] = ()
    activities: tuple[ActivityResult, ...] = ()
    indicators: tuple[IndicatorResult, ...] = ()

    def at(self, month: int) -> dict:
        """Headline figures for one month (1-based)."""
        i = month - 1
        return {
            "cum_plan": self.cum_plan[i],
            "cum_actual": self.cum_actual[i],
            "periodic_plan": self.periodic_plan[i],
            "periodic_actual": self.periodic_actual[i],
            "variance": self.variance[i],
            "status": self.status[i],
            "funds_total": self.funds_total,
            "funds_used_est": self.funds_used_est[i],
            "funds_used_actual": self.funds_used_actual[i],
            "funds_remaining": self.funds_remaining[i],
            "indicator_score": self.indicator_score[i],
        }


@dataclass(frozen=True)
class RankingRow:
    office_id: str
    value: Decimal | None  # None = no result: listed last, unranked
    rank: int | None
    label: str = ""

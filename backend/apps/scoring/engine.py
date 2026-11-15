"""Scoring engine (MASTERPLAN 7): pure functions over ``apps.scoring.types``.

No database access and no Django imports (enforced by tests/test_purity.py). Every score in the
product comes from here: results services, dashboards, exports and the plan editor preview.

Notation follows section 7: for activity a and month m (1..12), T = annual target, C = total cost,
p = planned per month, x = actual per month, S/P = cumulative actual/planned.
"""

from collections.abc import Iterable, Sequence
from decimal import ROUND_HALF_UP, Decimal, localcontext

from apps.scoring.types import (
    MONTHS,
    ONE,
    ZERO,
    ActivityInput,
    ActivityResult,
    IndicatorInput,
    IndicatorResult,
    OfficeResult,
    Profile,
    RankingRow,
    Series,
)

PRECISION = 34  # decimal digits for intermediate arithmetic
STATUS_PLACES = Decimal("1e-9")  # 7.4: round V to 9 places before comparing
RANK_PLACES = Decimal("1e-6")  # 7.8: ratio rounded to 6 places (= 4 places of a percent)
MEASURE_TYPES = ("quantity", "money", "recurring")


def _d(value) -> Decimal:
    if value is None:
        return ZERO
    return value if isinstance(value, Decimal) else Decimal(str(value))


def _cumulative(values: Iterable) -> Series:
    total, out = ZERO, []
    for v in values:
        total += _d(v)
        out.append(total)
    return tuple(out)


def _differences(cum: Series) -> Series:
    previous, out = ZERO, []
    for v in cum:
        out.append(v - previous)
        previous = v
    return tuple(out)


def _pad(values: Sequence) -> tuple:
    vals = tuple(values)[:MONTHS]
    return vals + (None,) * (MONTHS - len(vals))


# ---- 7.2 Weights ---------------------------------------------------------------------------------


def weights(activities: Sequence[ActivityInput], profile: Profile) -> list[Decimal]:
    """Weight of each activity under the profile's rule (7.2)."""
    n = len(activities)
    if n == 0:
        return []
    with localcontext() as ctx:
        ctx.prec = PRECISION
        if profile.weighting == "manual":
            return [_d(a.manual_weight) for a in activities]
        if profile.weighting == "cost_share":
            total = sum((_d(a.total_cost) for a in activities), ZERO)
            if total != ZERO:
                return [_d(a.total_cost) / total for a in activities]
        elif profile.weighting != "equal":
            raise ValueError(f"unknown weighting {profile.weighting!r}")
        return [ONE / n] * n


def manual_weights_valid(activities: Sequence[ActivityInput], tolerance: Decimal = Decimal("0.0001")) -> bool:
    """A plan under ``manual`` weighting can be approved only if the weights sum to 1 (±0.0001)."""
    total = sum((_d(a.manual_weight) for a in activities), ZERO)
    return abs(total - ONE) <= tolerance


# ---- 7.3 Activity progress -----------------------------------------------------------------------


def activity_progress(activity: ActivityInput, cap: bool) -> tuple[Series, Series, bool]:
    """Cumulative planned and actual ratios for months 1..12, and whether it has no target (7.3)."""
    if activity.measure_type not in MEASURE_TYPES:
        raise ValueError(f"unknown measure type {activity.measure_type!r}")
    planned = [_d(v) for v in _pad(activity.planned)]
    actual = [_d(v) for v in _pad(activity.actual)]
    zero = (ZERO,) * MONTHS
    with localcontext() as ctx:
        ctx.prec = PRECISION
        if activity.measure_type == "recurring":
            plan_months = [i for i, p in enumerate(planned) if p > ZERO]
            n = len(plan_months)
            if n == 0:
                return zero, zero, True
            counted, rp, ra, acc = 0, [], [], ZERO
            for i in range(MONTHS):
                if planned[i] > ZERO:
                    counted += 1
                    acc += actual[i] / planned[i]
                rp.append(Decimal(counted) / n)
                ra.append(acc / n)
        else:
            target = _d(activity.annual_target)
            if target == ZERO:
                return zero, zero, True
            rp = [c / target for c in _cumulative(planned)]
            ra = [c / target for c in _cumulative(actual)]
        if cap:
            ra = [min(v, ONE) for v in ra]
        return tuple(rp), tuple(ra), False


# ---- 7.4 Status ----------------------------------------------------------------------------------


def status(variance: Decimal, profile: Profile) -> str:
    """Ahead / on-time / delayed label for a variance, after rounding it to 9 places (7.4)."""
    v = _d(variance).quantize(STATUS_PLACES, rounding=ROUND_HALF_UP)
    t = _d(profile.on_time_tolerance)
    if v > t:
        return profile.label_ahead
    if v < -t:
        return profile.label_delayed
    return profile.label_on_time


# ---- 7.5 Indicators ------------------------------------------------------------------------------


def indicator_rate(indicator: IndicatorInput, cap: bool) -> Series:
    """r_i,m: cumulative (``sum``) or latest (``last``) actual over the annual target."""
    target = _d(indicator.annual_target)
    actual = _pad(indicator.actual)
    if target == ZERO:
        return (ZERO,) * MONTHS
    out, total, last = [], ZERO, ZERO
    with localcontext() as ctx:
        ctx.prec = PRECISION
        for v in actual:
            if v is not None:
                total += _d(v)
                last = _d(v)
            value = (total if indicator.aggregation != "last" else last) / target
            out.append(min(value, ONE) if cap else value)
    return tuple(out)


def _indicator_results(indicators: Sequence[IndicatorInput], profile: Profile) -> list[IndicatorResult]:
    n = len(indicators)
    if n == 0:
        return []
    with localcontext() as ctx:
        ctx.prec = PRECISION
        ws = [_d(i.weight) for i in indicators] if profile.indicator_weighting == "manual" else [ONE / n] * n
    return [
        IndicatorResult(id=i.id, weight=w, rate=indicator_rate(i, profile.cap_at_100))
        for i, w in zip(indicators, ws, strict=True)
    ]


def _weighted_score(results: Sequence[IndicatorResult]) -> tuple:
    if not results:
        return (None,) * MONTHS
    with localcontext() as ctx:
        ctx.prec = PRECISION
        return tuple(sum((r.weight * r.rate[m] for r in results), ZERO) for m in range(MONTHS))


def _mean_series(series: Sequence[Series]) -> tuple:
    if not series:
        return (None,) * MONTHS
    with localcontext() as ctx:
        ctx.prec = PRECISION
        n = Decimal(len(series))
        return tuple(sum((s[m] for s in series), ZERO) / n for m in range(MONTHS))


# ---- 7.4 Office result for one plan (and 7.7, the implementing view) -----------------------------


def _finish(
    cum_plan: Series,
    cum_actual: Series,
    funds_total: Decimal,
    funds_used_actual: tuple,
    profile: Profile,
    indicator_score: tuple,
    indicator_rates: tuple = (),
    activities: tuple = (),
    indicators: tuple = (),
) -> OfficeResult:
    with localcontext() as ctx:
        ctx.prec = PRECISION
        variance = tuple(a - p for a, p in zip(cum_actual, cum_plan, strict=True))
        est = tuple(funds_total * ca for ca in cum_actual)
        remaining = tuple(
            funds_total - (act if act is not None else e)
            for act, e in zip(funds_used_actual, est, strict=True)
        )
    return OfficeResult(
        cum_plan=cum_plan,
        cum_actual=cum_actual,
        periodic_plan=_differences(cum_plan),
        periodic_actual=_differences(cum_actual),
        variance=variance,
        status=tuple(status(v, profile) for v in variance),
        funds_total=funds_total,
        funds_used_est=est,
        funds_used_actual=funds_used_actual,
        funds_remaining=remaining,
        indicator_score=indicator_score,
        indicator_rates=indicator_rates,
        activities=activities,
        indicators=indicators,
    )


def _actual_amounts(activities: Sequence[ActivityInput]) -> tuple:
    """Σ actual_amount through m, or None for every month if no amount was ever entered (7.4)."""
    entered = any(v is not None for a in activities for v in _pad(a.actual_amount))
    if not entered:
        return (None,) * MONTHS
    monthly = [sum((_d(_pad(a.actual_amount)[m]) for a in activities), ZERO) for m in range(MONTHS)]
    return _cumulative(monthly)


def plan_result(
    activities: Sequence[ActivityInput], indicators: Sequence[IndicatorInput], profile: Profile
) -> OfficeResult:
    """The office result of one plan (7.2–7.5)."""
    ws = weights(activities, profile)
    act_results, cp, ca = [], [ZERO] * MONTHS, [ZERO] * MONTHS
    with localcontext() as ctx:
        ctx.prec = PRECISION
        for a, w in zip(activities, ws, strict=True):
            rp, ra, no_target = activity_progress(a, profile.cap_at_100)
            for m in range(MONTHS):
                cp[m] += w * rp[m]
                ca[m] += w * ra[m]
            act_results.append(
                ActivityResult(
                    id=a.id,
                    weight=w,
                    planned_ratio=rp,
                    actual_ratio=ra,
                    no_target=no_target,
                    zero_cost=_d(a.total_cost) == ZERO,
                )
            )
        funds_total = sum((_d(a.total_cost) for a in activities), ZERO)
    ind_results = _indicator_results(indicators, profile)
    return _finish(
        tuple(cp),
        tuple(ca),
        funds_total,
        _actual_amounts(activities),
        profile,
        _weighted_score(ind_results),
        indicator_rates=tuple(r.rate for r in ind_results),
        activities=tuple(act_results),
        indicators=tuple(ind_results),
    )


def implementing_result(activities: Sequence[ActivityInput], profile: Profile) -> OfficeResult:
    """7.7: every activity (from any approved plan) implemented by one office, weights re-normalised
    among them with the profile's rule. For display and ranking only, never for the owner roll-up."""
    return plan_result(activities, [], profile)


# ---- 7.6 Roll-up along the owner tree ------------------------------------------------------------


def rollup(components: Sequence[OfficeResult], profile: Profile) -> OfficeResult | None:
    """Combine an office's own plan result (if any) and its children's results (7.6).

    ``budget_weighted``: CA = Σ B_j·CA_j / Σ B_j (same for CP), B_j = component's funds_total; when
    every B_j is 0 it falls back to the simple average. ``simple_average``: unweighted mean.
    """
    if not components:
        return None
    with localcontext() as ctx:
        ctx.prec = PRECISION
        funds_total = sum((c.funds_total for c in components), ZERO)
        if profile.rollup == "budget_weighted" and funds_total != ZERO:
            cp = tuple(
                sum((c.funds_total * c.cum_plan[m] for c in components), ZERO) / funds_total
                for m in range(MONTHS)
            )
            ca = tuple(
                sum((c.funds_total * c.cum_actual[m] for c in components), ZERO) / funds_total
                for m in range(MONTHS)
            )
        elif profile.rollup in ("budget_weighted", "simple_average"):
            n = Decimal(len(components))
            cp = tuple(sum((c.cum_plan[m] for c in components), ZERO) / n for m in range(MONTHS))
            ca = tuple(sum((c.cum_actual[m] for c in components), ZERO) / n for m in range(MONTHS))
        else:
            raise ValueError(f"unknown rollup {profile.rollup!r}")

        if any(v is not None for c in components for v in c.funds_used_actual):
            used_actual = tuple(
                sum((c.funds_used_actual[m] or ZERO for c in components), ZERO) for m in range(MONTHS)
            )
        else:
            used_actual = (None,) * MONTHS

    all_rates = tuple(rate for c in components for rate in c.indicator_rates)
    if profile.indicator_rollup == "office_scores":
        scored = [c.indicator_score for c in components if c.indicator_score[0] is not None]
        score = _mean_series(scored)
    else:  # all_indicators: unweighted mean of every indicator in the subtree (workbook rule)
        score = _mean_series(all_rates)
    return _finish(cp, ca, funds_total, used_actual, profile, score, indicator_rates=all_rates)


# ---- 7.8 Ranking ---------------------------------------------------------------------------------


def ranking_value(result: OfficeResult | None, month: int, profile: Profile) -> Decimal | None:
    if result is None:
        return None
    i = month - 1
    if profile.ranking_metric == "cumulative_actual":
        return result.cum_actual[i]
    if profile.ranking_metric == "variance":
        return result.variance[i]
    if profile.ranking_metric == "actual_over_plan":
        plan = result.cum_plan[i]
        if plan == ZERO:
            return ZERO
        with localcontext() as ctx:
            ctx.prec = PRECISION
            return result.cum_actual[i] / plan
    raise ValueError(f"unknown ranking metric {profile.ranking_metric!r}")


def rank(values: Sequence[tuple[str, Decimal | None]], labels: dict | None = None) -> list[RankingRow]:
    """Rank (office id, value) pairs: descending on the value rounded to 6 places; equal values
    share a rank and the next rank skips (1, 1, 3); offices without a value come last, unranked.
    Ties are listed in the order given (pass them in tree order)."""
    labels = labels or {}
    scored = [(oid, v.quantize(RANK_PLACES, rounding=ROUND_HALF_UP)) for oid, v in values if v is not None]
    scored.sort(key=lambda item: item[1], reverse=True)  # stable: ties keep input order
    rows, previous, current_rank = [], None, 0
    for position, (oid, v) in enumerate(scored, start=1):
        if v != previous:
            current_rank = position
            previous = v
        rows.append(RankingRow(office_id=oid, value=v, rank=current_rank, label=labels.get(oid, "")))
    rows.extend(
        RankingRow(office_id=oid, value=None, rank=None, label=labels.get(oid, ""))
        for oid, v in values
        if v is None
    )
    return rows

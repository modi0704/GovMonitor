"""MASTERPLAN 7.5–7.8 and the roll-up / ranking vectors of 8.1 (P4.4)."""

from decimal import Decimal as D

import pytest

from apps.scoring import engine
from apps.scoring.tests.test_worked_example import act, months
from apps.scoring.types import IndicatorInput, Profile

WORKBOOK = Profile()


def flat_result(budget, ca, cp=None, indicators=()):
    """An office result with one activity whose cumulative actual is ``ca`` in every month."""
    cp = ca if cp is None else cp
    a = act("x", budget, 100, (D(str(cp)) * 100,), (D(str(ca)) * 100,))
    return engine.plan_result([a], list(indicators), WORKBOOK)


def ind(id, target, actual, **kw):
    return IndicatorInput(id=id, annual_target=D(str(target)), actual=months(*actual), **kw)


# ---- 7.5 indicators ------------------------------------------------------------------------------


def test_indicator_rates_sum_and_last():
    assert engine.indicator_rate(ind("s", 10, (2, 3, 5)), cap=False)[:3] == (D("0.2"), D("0.5"), D("1"))
    last = IndicatorInput(
        id="l", annual_target=D(80), actual=(D(40), None, D(60)) + (None,) * 9, aggregation="last"
    )
    assert engine.indicator_rate(last, cap=False)[:4] == (D("0.5"), D("0.5"), D("0.75"), D("0.75"))
    assert engine.indicator_rate(ind("o", 10, (15,)), cap=True)[0] == D(1)
    assert engine.indicator_rate(ind("z", 0, (5,)), cap=False)[0] == D(0)


def test_office_indicator_score_equal_and_manual():
    inds = [ind("a", 10, (5,)), ind("b", 10, (10,))]
    assert engine.plan_result([], inds, WORKBOOK).indicator_score[0] == D("0.75")
    manual = [ind("a", 10, (5,), weight=D("0.8")), ind("b", 10, (10,), weight=D("0.2"))]
    assert engine.plan_result([], manual, Profile(indicator_weighting="manual")).indicator_score[0] == D(
        "0.6"
    )
    assert engine.plan_result([], [], WORKBOOK).indicator_score[0] is None


# ---- 7.6 roll-up ---------------------------------------------------------------------------------


def test_rollup_vectors_of_8_1():
    x = flat_result(1_000_000, D("0.78"))
    y = flat_result(3_000_000, D("0.90"))
    assert engine.rollup([x, y], WORKBOOK).cum_actual[0] == D("0.87")
    assert engine.rollup([x, y], Profile(rollup="simple_average")).cum_actual[0] == D("0.84")


def test_rollup_derives_variance_status_and_funds():
    x = flat_result(1_000, D("0.5"), cp=D("0.6"))
    y = flat_result(3_000, D("0.9"), cp=D("0.8"))
    r = engine.rollup([x, y], WORKBOOK)
    assert r.funds_total == D(4000)
    assert r.cum_plan[0] == D("0.75") and r.cum_actual[0] == D("0.8")
    assert r.variance[0] == D("0.05") and r.status[0] == "ADVANCED"
    assert r.funds_used_est[0] == D(3200) and r.funds_used_actual[0] is None


def test_rollup_applies_at_every_level():
    a, b, c = flat_result(100, D("0.2")), flat_result(300, D("0.6")), flat_result(400, D("1"))
    child = engine.rollup([a, b], WORKBOOK)  # B = 400, CA = 0.5
    parent = engine.rollup([child, c], WORKBOOK)  # (400·0.5 + 400·1) / 800
    assert child.funds_total == D(400) and child.cum_actual[0] == D("0.5")
    assert parent.cum_actual[0] == D("0.75")


def test_rollup_of_zero_budgets_falls_back_to_simple_average():
    r = engine.rollup([flat_result(0, D("0.2")), flat_result(0, D("0.4"))], WORKBOOK)
    assert r.cum_actual[0] == D("0.3")


def test_rollup_edge_cases():
    assert engine.rollup([], WORKBOOK) is None
    with pytest.raises(ValueError):
        engine.rollup([flat_result(1, D("0.1"))], Profile(rollup="median"))


def test_rollup_sums_actual_amounts_when_any_component_has_them():
    spent = engine.plan_result(
        [act("a", 100, 1, (1,), (1,), actual_amount=(D(70),) + (None,) * 11)], [], WORKBOOK
    )
    r = engine.rollup([spent, flat_result(100, D("0.5"))], WORKBOOK)
    assert r.funds_used_actual[0] == D(70) and r.funds_remaining[0] == D(130)


def test_indicator_rollup_rules():
    one = flat_result(100, D("0.5"), indicators=[ind("a", 10, (10,))])  # score 1.0
    three = flat_result(
        100, D("0.5"), indicators=[ind("b", 10, (0,)), ind("c", 10, (0,)), ind("d", 10, (0,))]
    )
    every = engine.rollup([one, three], WORKBOOK)  # mean of 4 indicators: (1+0+0+0)/4
    assert every.indicator_score[0] == D("0.25") and len(every.indicator_rates) == 4
    by_office = engine.rollup([one, three], Profile(indicator_rollup="office_scores"))  # (1 + 0) / 2
    assert by_office.indicator_score[0] == D("0.5")
    assert engine.rollup([flat_result(1, D("0.1"))], WORKBOOK).indicator_score[0] is None


# ---- 7.7 implementing view -----------------------------------------------------------------------


def test_implementing_view_renormalises_weights():
    # Two activities from different owners' plans, implemented by one field unit.
    from_div_a = act("a1", 600, 10, (10,), (5,), implementing_office_id="unit")
    from_div_b = act("b1", 200, 4, (4,), (4,), implementing_office_id="unit")
    r = engine.implementing_result([from_div_a, from_div_b], WORKBOOK)
    assert [x.weight for x in r.activities] == [D("0.75"), D("0.25")]
    assert r.cum_actual[0] == D("0.625")  # 0.75·0.5 + 0.25·1


# ---- 7.8 ranking ---------------------------------------------------------------------------------


def test_ranking_ties_share_and_skip():
    rows = engine.rank([("x", D("0.80")), ("y", D("0.90")), ("z", D("0.90"))])
    assert [(r.office_id, r.rank) for r in rows] == [("y", 1), ("z", 1), ("x", 3)]


def test_ranking_rounds_to_six_places_and_lists_missing_last():
    rows = engine.rank(
        [("a", D("0.9000004")), ("none", None), ("b", D("0.8999996")), ("c", D("0.5"))], labels={"a": "A"}
    )
    assert [(r.office_id, r.rank) for r in rows] == [("a", 1), ("b", 1), ("c", 3), ("none", None)]
    assert rows[0].label == "A" and rows[-1].value is None


def test_ranking_metrics():
    r = flat_result(100, D("0.45"), cp=D("0.5"))
    assert engine.ranking_value(r, 1, WORKBOOK) == D("0.45")
    assert engine.ranking_value(r, 1, Profile(ranking_metric="variance")) == D("-0.05")
    assert engine.ranking_value(r, 1, Profile(ranking_metric="actual_over_plan")) == D("0.9")
    zero_plan = flat_result(100, D("0"), cp=D("0"))
    assert engine.ranking_value(zero_plan, 1, Profile(ranking_metric="actual_over_plan")) == D(0)
    assert engine.ranking_value(None, 1, WORKBOOK) is None
    with pytest.raises(ValueError):
        engine.ranking_value(r, 1, Profile(ranking_metric="vibes"))


def test_manual_weights_validation_helper():
    good = [
        act("a", 1, 1, (1,), (1,), manual_weight=D("0.33335")),
        act("b", 1, 1, (1,), (1,), manual_weight=D("0.66665")),
    ]
    bad = [
        act("a", 1, 1, (1,), (1,), manual_weight=D("0.5")),
        act("b", 1, 1, (1,), (1,), manual_weight=D("0.4")),
    ]
    assert engine.manual_weights_valid(good) and not engine.manual_weights_valid(bad)
    with pytest.raises(ValueError):
        engine.weights(good, Profile(weighting="random"))


def test_quarter_and_year_to_date_windows():
    from apps.scoring.tests.test_worked_example import worked

    r = engine.plan_result(worked(), [], WORKBOOK)
    q = engine.quarter_summaries(r.cum_plan, r.cum_actual, 3, WORKBOOK)
    assert len(q) == 1 and q[0]["first"] == 1 and q[0]["last"] == 3 and not q[0]["partial"]
    assert (q[0]["plan"], q[0]["actual"], q[0]["status"]) == (D("1.00"), D("0.78"), "DELAYED")
    feb_on = engine.window_summary(r.cum_plan, r.cum_actual, 2, 3, WORKBOOK)
    assert (feb_on["plan"], feb_on["actual"]) == (D("0.88"), D("0.66"))
    later = engine.quarter_summaries(r.cum_plan, r.cum_actual, 5, WORKBOOK)
    assert [(x["quarter"], x["partial"]) for x in later] == [(1, False), (2, True)]
    assert later[1]["plan"] == D(0) and later[1]["status_kind"] == "on_time"
    with pytest.raises(ValueError):
        engine.window_summary(r.cum_plan, r.cum_actual, 3, 2, WORKBOOK)

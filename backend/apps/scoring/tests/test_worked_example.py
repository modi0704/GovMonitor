"""MASTERPLAN 8.1 worked example and the rules of 7.2–7.4 (P4.3). Written before the engine."""

from decimal import Decimal as D

import pytest

from apps.scoring import engine
from apps.scoring.types import ActivityInput, Profile

WORKBOOK = Profile()
CAPPED = Profile(cap_at_100=True)


def months(*values):
    """Pad monthly values to 12 months with zeros."""
    vals = [D(str(v)) for v in values]
    return tuple(vals + [D(0)] * (12 - len(vals)))


def act(id, cost, target, plan, actual, **kw):
    return ActivityInput(
        id=id,
        measure_type=kw.pop("measure_type", "quantity"),
        annual_target=D(str(target)),
        total_cost=D(str(cost)),
        planned=months(*plan),
        actual=months(*actual),
        **kw,
    )


def worked(b_march=3):
    return [
        act("A", 600_000, 10, (2, 3, 5), (2, 2, 4)),
        act("B", 300_000, 4, (0, 2, 2), (0, 1, b_march)),
        act("C", 100_000, 1, (0, 0, 1), (0, 0, 0)),
    ]


def test_cost_share_weights():
    assert engine.weights(worked(), WORKBOOK) == [D("0.6"), D("0.3"), D("0.1")]


def test_worked_example_cumulative_variance_status():
    r = engine.plan_result(worked(), [], WORKBOOK)
    assert r.cum_plan[:3] == (D("0.12"), D("0.45"), D("1.00"))
    assert r.cum_actual[:3] == (D("0.12"), D("0.315"), D("0.78"))
    assert r.variance[:3] == (D(0), D("-0.135"), D("-0.22"))
    assert r.status[:3] == ("ON-TIME", "DELAYED", "DELAYED")
    assert r.periodic_plan[:3] == (D("0.12"), D("0.33"), D("0.55"))
    assert r.periodic_actual[:3] == (D("0.12"), D("0.195"), D("0.465"))


def test_worked_example_march_funds():
    r = engine.plan_result(worked(), [], WORKBOOK)
    march = r.at(3)
    assert march["funds_total"] == D(1_000_000)
    assert march["funds_used_est"] == D(780_000)
    assert march["funds_remaining"] == D(220_000)
    assert march["funds_used_actual"] is None


def test_over_delivery_with_and_without_cap():
    assert engine.plan_result(worked(b_march=5), [], WORKBOOK).cum_actual[2] == D("0.93")
    assert engine.plan_result(worked(b_march=5), [], CAPPED).cum_actual[2] == D("0.78")


def test_months_after_the_last_report_stay_flat():
    r = engine.plan_result(worked(), [], WORKBOOK)
    assert r.cum_actual[11] == D("0.78") and r.cum_plan[11] == D("1.00")
    assert r.periodic_actual[3:] == (D(0),) * 9


# ---- 7.2 weights ------------------------------------------------------------------------------


def test_equal_and_manual_weights():
    acts = worked()
    equal = engine.weights(acts, Profile(weighting="equal"))
    assert len(set(equal)) == 1 and abs(equal[0] - D(1) / 3) < D("1e-27") and abs(sum(equal) - 1) < D("1e-25")
    manual = [
        act("A", 1, 1, (1,), (1,), manual_weight=D("0.5")),
        act("B", 1, 1, (1,), (0,), manual_weight=D("0.5")),
    ]
    assert engine.weights(manual, Profile(weighting="manual")) == [D("0.5"), D("0.5")]
    assert engine.plan_result(manual, [], Profile(weighting="manual")).cum_actual[0] == D("0.5")


def test_cost_share_falls_back_to_equal_when_no_costs():
    acts = [act("A", 0, 1, (1,), (1,)), act("B", 0, 1, (1,), (0,))]
    assert engine.weights(acts, WORKBOOK) == [D("0.5"), D("0.5")]


def test_zero_cost_activity_has_weight_zero_and_is_flagged():
    acts = [act("A", 100, 1, (1,), (1,)), act("Z", 0, 1, (1,), (0,))]
    r = engine.plan_result(acts, [], WORKBOOK)
    assert [a.weight for a in r.activities] == [D(1), D(0)]
    assert [a.zero_cost for a in r.activities] == [False, True]
    assert r.cum_actual[0] == D(1)


def test_no_activities():
    r = engine.plan_result([], [], WORKBOOK)
    assert r.cum_plan == (D(0),) * 12 and r.funds_total == D(0) and r.status[0] == "ON-TIME"


# ---- 7.3 progress by measure type -------------------------------------------------------------


def test_money_measure_uses_amounts():
    # T = planned total amount, x = amount disbursed.
    gas = act("G", 1000, 1000, (400, 600), (300, 500), measure_type="money")
    r = engine.plan_result([gas], [], WORKBOOK)
    assert r.cum_plan[:2] == (D("0.4"), D("1"))
    assert r.cum_actual[:2] == (D("0.3"), D("0.8"))


def test_recurring_measure():
    # A level maintained in months 1–4 (e.g. 50 scholars paid each month): n = 4.
    rec = act("R", 100, 50, (50, 50, 50, 50), (50, 40, 50, 0), measure_type="recurring")
    rp, ra, no_target = engine.activity_progress(rec, cap=False)
    assert rp[:4] == (D("0.25"), D("0.5"), D("0.75"), D("1"))
    assert ra[:4] == (D("0.25"), D("0.45"), D("0.70"), D("0.70"))
    assert not no_target


def test_recurring_ignores_months_without_plan_and_caps_total():
    rec = act("R", 100, 10, (10, 0, 10), (20, 99, 10), measure_type="recurring")
    rp, ra, _ = engine.activity_progress(rec, cap=False)
    assert rp[:3] == (D("0.5"), D("0.5"), D("1"))
    assert ra[:3] == (D("1"), D("1"), D("1.5"))  # month 2 has no plan: its 99 is ignored
    _, capped, _ = engine.activity_progress(rec, cap=True)
    assert capped[2] == D(1)


def test_no_target_gives_zero_ratios():
    for a in (
        act("Q", 100, 0, (0,), (5,)),
        act("R", 100, 10, (0,), (5,), measure_type="recurring"),  # n = 0
    ):
        rp, ra, no_target = engine.activity_progress(a, cap=False)
        assert no_target and rp == (D(0),) * 12 and ra == (D(0),) * 12


def test_unknown_measure_type_is_rejected():
    with pytest.raises(ValueError):
        engine.activity_progress(act("X", 1, 1, (1,), (1,), measure_type="weird"), cap=False)


# ---- 7.4 status and funds ---------------------------------------------------------------------


def test_status_rounding_removes_float_residue():
    assert engine.status(D("-5.55E-17"), WORKBOOK) == "ON-TIME"
    assert engine.status(D("-0.000000001"), WORKBOOK) == "DELAYED"
    assert engine.status(D("0.0001"), WORKBOOK) == "ADVANCED"


def test_status_with_tolerance_and_custom_labels():
    p = Profile(on_time_tolerance=D("0.02"), label_ahead="AHEAD", label_on_time="OK", label_delayed="LATE")
    assert [engine.status(D(v), p) for v in ("0.03", "0.02", "-0.02", "-0.021")] == [
        "AHEAD",
        "OK",
        "OK",
        "LATE",
    ]


def test_funds_use_actual_amounts_when_entered():
    a = act("A", 1000, 10, (5, 5), (5, 0), actual_amount=(D(300), None) + (None,) * 10)
    b = act("B", 1000, 10, (5, 5), (5, 5))
    r = engine.plan_result([a, b], [], WORKBOOK)
    assert r.funds_used_actual[0] == D(300) and r.funds_used_actual[1] == D(300)
    assert r.funds_remaining[0] == D(1700)  # actual wins over the estimate
    assert r.funds_used_est[1] == D(2000) * r.cum_actual[1]


def test_status_kind_matches_label():
    p = Profile(on_time_tolerance=D("0.02"), label_ahead="AHEAD")
    assert [engine.status_kind(D(v), p) for v in ("0.03", "0", "-0.03")] == ["ahead", "on_time", "delayed"]
    assert engine.status(D("0.03"), p) == "AHEAD"

"""Property tests (P4.7) with seeded random generators (D22): reproducible, no extra dependency."""

import random
from decimal import Decimal as D

import pytest

from apps.scoring import engine
from apps.scoring.types import ActivityInput, IndicatorInput, Profile

CASES = 300
TOL = D("1e-25")


def random_activity(rng: random.Random, i: int) -> ActivityInput:
    kind = rng.choice(["quantity", "quantity", "money", "recurring"])
    planned = [D(rng.choice([0, 0, rng.randint(1, 50)])) for _ in range(12)]
    actual = [D(rng.randint(0, 60)) if rng.random() < 0.7 else None for _ in range(12)]
    target = sum(planned) if rng.random() < 0.9 else D(rng.randint(0, 100))
    return ActivityInput(
        id=f"a{i}",
        measure_type=kind,
        annual_target=target,
        total_cost=D(rng.choice([0, rng.randint(1, 5_000_000)])),
        planned=tuple(planned),
        actual=tuple(actual),
    )


def random_plan(rng: random.Random):
    acts = [random_activity(rng, i) for i in range(rng.randint(1, 12))]
    inds = [
        IndicatorInput(
            id=f"i{j}",
            annual_target=D(rng.randint(0, 40)),
            actual=tuple(D(rng.randint(0, 10)) for _ in range(12)),
        )
        for j in range(rng.randint(0, 4))
    ]
    return acts, inds


def profiles(rng):
    return Profile(
        weighting=rng.choice(["cost_share", "equal"]),
        cap_at_100=rng.choice([True, False]),
        rollup=rng.choice(["budget_weighted", "simple_average"]),
        indicator_rollup=rng.choice(["all_indicators", "office_scores"]),
    )


@pytest.mark.parametrize("seed", range(3))
def test_weights_sum_to_one(seed):
    rng = random.Random(seed)
    for _ in range(CASES):
        acts, _ = random_plan(rng)
        for p in (Profile(weighting="cost_share"), Profile(weighting="equal")):
            assert abs(sum(engine.weights(acts, p)) - 1) < TOL


@pytest.mark.parametrize("seed", range(3))
def test_cumulative_series_never_decrease(seed):
    rng = random.Random(100 + seed)
    for _ in range(CASES):
        acts, inds = random_plan(rng)
        r = engine.plan_result(acts, inds, profiles(rng))
        for series in (r.cum_plan, r.cum_actual):
            assert all(b >= a - TOL for a, b in zip(series, series[1:], strict=False))
        assert all(x >= -TOL for x in r.periodic_actual)


@pytest.mark.parametrize("seed", range(3))
def test_capped_offices_never_exceed_one(seed):
    rng = random.Random(200 + seed)
    capped = Profile(cap_at_100=True)
    for _ in range(CASES // 3):
        children = [engine.plan_result(*random_plan(rng), capped) for _ in range(rng.randint(1, 4))]
        for r in [*children, engine.rollup(children, capped)]:
            assert max(r.cum_actual) <= 1 + TOL
            for a in r.activities:
                assert max(a.actual_ratio) <= 1


@pytest.mark.parametrize("seed", range(3))
def test_budget_weighted_rollup_of_identical_children_equals_the_child(seed):
    rng = random.Random(300 + seed)
    p = Profile()
    for _ in range(CASES // 3):
        child = engine.plan_result(*random_plan(rng), p)
        parent = engine.rollup([child] * rng.randint(2, 5), p)
        for a, b in zip(parent.cum_actual, child.cum_actual, strict=True):
            assert abs(a - b) < TOL
        for a, b in zip(parent.cum_plan, child.cum_plan, strict=True):
            assert abs(a - b) < TOL
        assert parent.status == child.status

"""The results printed in the user-facing text files must match the real scoring engine."""

from decimal import Decimal

from apps.scoring.engine import plan_result
from apps.scoring.presets import load_preset
from apps.scoring.types import ActivityInput


def test_practice_january_delay_and_february_catch_up():
    d = Decimal
    result = plan_result(
        [
            ActivityInput(
                id="ACT-01",
                measure_type="quantity",
                annual_target=d(12),
                total_cost=d(60000),
                planned=(d(1),) * 12,
                actual=(d(1), d(1)) + (None,) * 10,
            ),
            ActivityInput(
                id="ACT-02",
                measure_type="quantity",
                annual_target=d(120),
                total_cost=d(40000),
                planned=(d(10),) * 12,
                actual=(d(8), d(12)) + (None,) * 10,
            ),
        ],
        [],
        load_preset("workbook_compatible"),
    )

    def percent(value):
        return (value * 100).quantize(d("0.01"))

    assert [percent(x) for x in result.cum_actual[:2]] == [d("7.67"), d("16.67")]
    assert [percent(x) for x in result.periodic_actual[:2]] == [d("7.67"), d("9.00")]
    assert [percent(x) for x in result.cum_plan[:2]] == [d("8.33"), d("16.67")]
    assert [percent(x) for x in result.variance[:2]] == [d("-0.67"), d("0.00")]
    assert result.status[:2] == ("DELAYED", "ON-TIME")
    assert [x.quantize(d("0.01")) for x in result.funds_used_est[:2]] == [d("7666.67"), d("16666.67")]
    assert [x.quantize(d("0.01")) for x in result.funds_remaining[:2]] == [d("92333.33"), d("83333.33")]
    assert result.funds_used_actual[:2] == (None, None)

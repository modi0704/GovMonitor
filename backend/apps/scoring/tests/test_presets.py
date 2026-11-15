from decimal import Decimal as D

import pytest

from apps.scoring import presets
from apps.scoring.types import Profile


@pytest.mark.parametrize("name", sorted(presets.PRESETS))
def test_every_preset_loads_into_a_valid_profile(name):
    profile = presets.load_preset(name)
    assert profile.preset == name
    assert presets.validate(profile) is profile
    assert presets.matches_preset(profile) == name
    assert name in presets.PRESET_DESCRIPTIONS


def test_workbook_compatible_is_the_default_and_matches_7_10():
    p = presets.load_preset(presets.DEFAULT_PRESET)
    assert (p.weighting, p.cap_at_100, p.on_time_tolerance, p.rollup) == (
        "cost_share",
        False,
        D(0),
        "budget_weighted",
    )
    assert (p.label_ahead, p.label_on_time, p.label_delayed) == ("ADVANCED", "ON-TIME", "DELAYED")
    assert (p.indicator_weighting, p.indicator_rollup, p.ranking_metric) == (
        "equal",
        "all_indicators",
        "cumulative_actual",
    )
    assert p == Profile()  # the engine's defaults are the workbook rules


def test_capped_with_tolerance():
    p = presets.load_preset("capped_with_tolerance")
    assert p.cap_at_100 is True and p.on_time_tolerance == D("0.02")


def test_validation_rejects_bad_settings():
    with pytest.raises(presets.InvalidProfile):
        presets.load_preset("nope")
    for bad in (
        Profile(weighting="random"),
        Profile(on_time_tolerance=D("-0.1")),
        Profile(on_time_tolerance=D("1")),
        Profile(label_delayed=" "),
        Profile(ranking_metric="x"),
        Profile(cap_at_100="yes"),
    ):
        with pytest.raises(presets.InvalidProfile):
            presets.validate(bad)


def test_profile_from_stored_settings():
    p = presets.profile_from_settings(
        {"preset": "capped_with_tolerance", "on_time_tolerance": "0.05", "x": 1}
    )
    assert p.cap_at_100 and p.on_time_tolerance == D("0.05") and presets.matches_preset(p) is None
    assert presets.profile_from_settings({}) == Profile()

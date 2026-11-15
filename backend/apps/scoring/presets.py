"""Scoring presets as data (MASTERPLAN 7.10, P4.5) and profile validation.

A fiscal year's scoring profile starts from a preset; every setting can then be changed per agency
per fiscal year. Adding a preset = adding an entry here.
"""

from dataclasses import fields, replace
from decimal import Decimal

from apps.scoring.types import Profile

ALLOWED = {
    "weighting": ("cost_share", "equal", "manual"),
    "rollup": ("budget_weighted", "simple_average"),
    "indicator_weighting": ("equal", "manual"),
    "indicator_rollup": ("all_indicators", "office_scores"),
    "ranking_metric": ("cumulative_actual", "variance", "actual_over_plan"),
}

_WORKBOOK = {
    "weighting": "cost_share",
    "cap_at_100": False,
    "on_time_tolerance": Decimal("0"),
    "label_ahead": "ADVANCED",
    "label_on_time": "ON-TIME",
    "label_delayed": "DELAYED",
    "rollup": "budget_weighted",
    "indicator_weighting": "equal",
    "indicator_rollup": "all_indicators",
    "ranking_metric": "cumulative_actual",
}

PRESETS: dict[str, dict] = {
    # Reproduces the Excel method exactly (D5). Default for new fiscal years.
    "workbook_compatible": dict(_WORKBOOK),
    # As above, but no office can exceed 100% and ±2 points count as on time.
    "capped_with_tolerance": {**_WORKBOOK, "cap_at_100": True, "on_time_tolerance": Decimal("0.02")},
}

PRESET_DESCRIPTIONS = {
    "workbook_compatible": "Same results as the agency's Excel workbook: weights by cost, no 100% ceiling, "
    "no tolerance, offices rolled up by budget.",
    "capped_with_tolerance": "Like the workbook, but over-delivery counts at most 100% and results within "
    "2 percentage points of plan are on time.",
}

DEFAULT_PRESET = "workbook_compatible"


class InvalidProfile(ValueError):
    pass


def load_preset(name: str) -> Profile:
    if name not in PRESETS:
        raise InvalidProfile(f"unknown preset {name!r}")
    profile = Profile(preset=name, **PRESETS[name])
    validate(profile)
    return profile


def validate(profile: Profile) -> Profile:
    problems = []
    for name, allowed in ALLOWED.items():
        if getattr(profile, name) not in allowed:
            problems.append(f"{name} must be one of {', '.join(allowed)}")
    tolerance = profile.on_time_tolerance
    if not isinstance(tolerance, Decimal) or tolerance < 0 or tolerance >= 1:
        problems.append("on_time_tolerance must be a ratio from 0 up to (not including) 1")
    if not isinstance(profile.cap_at_100, bool):
        problems.append("cap_at_100 must be true or false")
    for name in ("label_ahead", "label_on_time", "label_delayed"):
        if not str(getattr(profile, name)).strip():
            problems.append(f"{name} must not be empty")
    if problems:
        raise InvalidProfile("; ".join(problems))
    return profile


def profile_from_settings(settings: dict) -> Profile:
    """Build a profile from stored settings (unknown keys ignored, missing keys from the preset)."""
    base = (
        load_preset(settings.get("preset", DEFAULT_PRESET))
        if settings.get("preset") in PRESETS
        else Profile()
    )
    names = {f.name for f in fields(Profile)}
    values = {k: v for k, v in settings.items() if k in names}
    if "on_time_tolerance" in values:
        values["on_time_tolerance"] = Decimal(str(values["on_time_tolerance"]))
    return validate(replace(base, **values))


def matches_preset(profile: Profile) -> str | None:
    """Name of the preset whose settings this profile has exactly, if any."""
    for name, settings in PRESETS.items():
        if all(getattr(profile, k) == v for k, v in settings.items()):
            return name
    return None

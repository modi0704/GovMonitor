"""Fiscal years, periods and scoring profiles (MASTERPLAN 6.4, P5.2)."""

import calendar
import datetime
import zoneinfo

from django.db import transaction

from apps.audit import services as audit
from apps.planning.models import FiscalYear, ReportingPeriod, ScoringProfile
from apps.scoring import presets
from apps.tenancy.models import Agency


class PlanningError(Exception):
    def __init__(self, code: str, message: str, **extra):
        super().__init__(message)
        self.code = code
        self.message = message
        self.extra = extra


def add_months(year: int, month: int, n: int) -> tuple[int, int]:
    index = year * 12 + (month - 1) + n
    return index // 12, index % 12 + 1


def month_bounds(year: int, month: int) -> tuple[datetime.date, datetime.date]:
    last = calendar.monthrange(year, month)[1]
    return datetime.date(year, month, 1), datetime.date(year, month, last)


def cutoff_for(year: int, month: int, cutoff_day: int, tz_name: str) -> datetime.datetime:
    """End of ``cutoff_day`` of the month after (year, month), in the agency's time zone (D4)."""
    ny, nm = add_months(year, month, 1)
    local = datetime.datetime(ny, nm, cutoff_day, 23, 59, 59, tzinfo=zoneinfo.ZoneInfo(tz_name))
    return local.astimezone(datetime.UTC)


def fiscal_year_months(start_year: int, start_month: int) -> list[tuple[int, int]]:
    return [add_months(start_year, start_month, i) for i in range(12)]


@transaction.atomic
def create_fiscal_year(label: str, start_year: int, preset: str = presets.DEFAULT_PRESET) -> FiscalYear:
    """Create a fiscal year with its 12 periods (from the agency's start month) and a scoring
    profile from ``preset`` (P5.2)."""
    agency = Agency.objects.get()
    label = (label or "").strip()
    if not label:
        raise PlanningError("label_required", "Give the fiscal year a label, e.g. 2026.")
    if FiscalYear.objects.filter(label__iexact=label).exists():
        raise PlanningError("duplicate_label", f"Fiscal year {label} already exists.")
    months = fiscal_year_months(start_year, agency.fiscal_year_start_month)
    start = month_bounds(*months[0])[0]
    end = month_bounds(*months[-1])[1]
    if FiscalYear.objects.filter(start_date__lte=end, end_date__gte=start).exists():
        raise PlanningError("overlap", "This fiscal year overlaps an existing one.")
    fy = FiscalYear.objects.create(label=label, start_date=start, end_date=end)
    settings = presets.PRESETS.get(preset)
    if settings is None:
        raise PlanningError("unknown_preset", f"Unknown scoring preset {preset!r}.")
    profile = ScoringProfile.objects.create(fiscal_year=fy, preset=preset, **settings)
    with audit.suppressed():  # one "create" for the year is enough; periods are derived
        ReportingPeriod.objects.bulk_create(
            [
                ReportingPeriod(
                    fiscal_year=fy,
                    month_index=i + 1,
                    start_date=month_bounds(y, m)[0],
                    end_date=month_bounds(y, m)[1],
                    cutoff_at=cutoff_for(y, m, profile.cutoff_day, agency.timezone),
                )
                for i, (y, m) in enumerate(months)
            ]
        )
    return fy


def set_fiscal_year_status(fy: FiscalYear, status: str) -> FiscalYear:
    allowed = {"draft": {"open"}, "open": {"closed"}, "closed": {"open"}}
    if status not in allowed.get(fy.status, set()):
        raise PlanningError("bad_transition", f"A {fy.status} fiscal year cannot become {status}.")
    fy.status = status
    fy.save(update_fields=["status"])
    return fy


def has_locked_period(fy: FiscalYear) -> bool:
    return fy.periods.filter(status=ReportingPeriod.Status.LOCKED).exists()


PROFILE_EDITABLE = (
    *ScoringProfile.ENGINE_FIELDS,
    "mov_required",
    "auto_lock",
    "cutoff_day",
    "show_actual_amounts",
)


@transaction.atomic
def update_profile(profile: ScoringProfile, changes: dict, *, confirm: bool = False) -> ScoringProfile:
    """Change scoring settings (P5.2). ``preset`` first applies that preset's settings, then any
    explicit changes. After a period of the year is locked, a change needs ``confirm=True``; locked
    results never change because they are read from their snapshot (P7.3)."""
    changes = {k: v for k, v in changes.items() if k in PROFILE_EDITABLE}
    if "preset" in changes and changes["preset"] in presets.PRESETS:
        changes = {**presets.PRESETS[changes["preset"]], **changes}
    current = {f: getattr(profile, f) for f in PROFILE_EDITABLE}
    proposed = {**current, **changes}
    engine_settings = {k: proposed[k] for k in ScoringProfile.ENGINE_FIELDS}
    try:
        engine_profile = presets.profile_from_settings(engine_settings)
    except presets.InvalidProfile as exc:
        raise PlanningError("invalid_profile", str(exc)) from exc
    if not 1 <= int(proposed["cutoff_day"]) <= 28:
        raise PlanningError("invalid_profile", "The cutoff day must be between 1 and 28.")
    normalised = {**proposed, "on_time_tolerance": engine_profile.on_time_tolerance}
    if "preset" not in changes or changes.get("preset") not in presets.PRESETS:
        normalised["preset"] = presets.matches_preset(engine_profile) or "custom"
    differs = {k: v for k, v in normalised.items() if getattr(profile, k) != v}
    if not differs:
        return profile
    if has_locked_period(profile.fiscal_year) and not confirm:
        raise PlanningError(
            "confirm_required",
            "Some months of this year are locked. Their results will not change, but open months will "
            "be scored with the new settings. Confirm to continue.",
        )
    for k, v in differs.items():
        setattr(profile, k, v)
    profile.version += 1
    profile.save()
    if "cutoff_day" in differs:
        agency = Agency.objects.get()
        for period in profile.fiscal_year.periods.filter(status=ReportingPeriod.Status.OPEN):
            y, m = period.start_date.year, period.start_date.month
            period.cutoff_at = cutoff_for(y, m, profile.cutoff_day, agency.timezone)
            period.save(update_fields=["cutoff_at"])
    return profile

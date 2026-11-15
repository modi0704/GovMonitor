"""Who may report what, when (MASTERPLAN P6.4, D6).

An activity's accomplishment can be saved only while the period is open and the owning office's
submission for that month is a draft or returned, and only by a user who can edit the plan's office
or the activity's implementing office (field units report their own activities).
"""

from dataclasses import dataclass

from apps.accounts import permissions as perm
from apps.planning.models import Activity, Indicator, Plan, ReportingPeriod
from apps.reporting.models import OfficeSubmission


class ReportingError(Exception):
    def __init__(self, code: str, message: str, http: int = 400, **extra):
        super().__init__(message)
        self.code = code
        self.message = message
        self.http = http
        self.extra = extra


def approved_plan(office, fiscal_year) -> Plan | None:
    return Plan.objects.filter(office=office, fiscal_year=fiscal_year, status=Plan.Status.APPROVED).first()


def submission_for(office, period: ReportingPeriod, create: bool = True) -> OfficeSubmission | None:
    sub = OfficeSubmission.objects.filter(office=office, period=period).first()
    if sub is None and create:
        sub = OfficeSubmission.objects.create(office=office, period=period)
    return sub


@dataclass
class ActivityRef:
    activity: Activity
    plan: Plan

    @property
    def owner_office(self):
        return self.plan.office

    @property
    def implementing_office(self):
        return self.activity.implementing_office or self.plan.office


def activity_in_period(lineage_id, period: ReportingPeriod) -> ActivityRef | None:
    """The activity with this lineage in the currently approved plan of the period's fiscal year."""
    act = (
        Activity.objects.select_related("plan__office", "implementing_office")
        .filter(
            lineage_id=lineage_id,
            row_kind=Activity.RowKind.ACTIVITY,
            plan__fiscal_year_id=period.fiscal_year_id,
            plan__status=Plan.Status.APPROVED,
        )
        .first()
    )
    return ActivityRef(act, act.plan) if act else None


def indicator_in_period(lineage_id, period: ReportingPeriod) -> Indicator | None:
    return (
        Indicator.objects.select_related("plan__office")
        .filter(
            lineage_id=lineage_id,
            plan__fiscal_year_id=period.fiscal_year_id,
            plan__status=Plan.Status.APPROVED,
        )
        .first()
    )


def can_view_activity(user, ref: ActivityRef) -> bool:
    return perm.can_view(user, ref.owner_office) or perm.can_view(user, ref.implementing_office)


def can_edit_activity(user, ref: ActivityRef) -> bool:
    return perm.can_edit(user, ref.owner_office) or perm.can_edit(user, ref.implementing_office)


def check_period_open(period: ReportingPeriod) -> None:
    if period.status == ReportingPeriod.Status.LOCKED:
        raise ReportingError("period_locked", "This month is locked; nothing can be changed.", http=409)


def check_submission_editable(owner_office, period: ReportingPeriod) -> OfficeSubmission:
    sub = submission_for(owner_office, period)
    if not sub.editable:
        raise ReportingError(
            "submission_closed",
            f"The {owner_office.code} report for this month is {sub.status}; "
            "it can be changed only after it is returned for correction.",
            http=409,
        )
    return sub


def check_can_report_activity(user, ref: ActivityRef, period: ReportingPeriod) -> None:
    """All P6.4 rules for one activity in one period; raises ReportingError."""
    if not can_view_activity(user, ref):
        raise ReportingError("not_found", "No such activity.", http=404)
    if not can_edit_activity(user, ref):
        raise ReportingError("read_only", "You have read-only access to this activity.", http=403)
    check_period_open(period)
    check_submission_editable(ref.owner_office, period)

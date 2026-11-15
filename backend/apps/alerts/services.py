"""Alerts (MASTERPLAN P11.2): the daily scan, event notifications and who receives what.

Every notification carries a ``dedupe_key`` that names the alert and its recipient; inserts ignore
keys that already exist, so running the scan twice (or replaying an event) sends nothing twice.

Recipients (D38):

* "admins of an office": users with an ``admin`` assignment at that office; when it has none, at
  the nearest ancestor that has one.
* "agency administrators": ``admin`` assignments at the root office.
* "users of an office and its ancestors": any assignment (admin or read-only) at the office or
  above it.
"""

import datetime
import zoneinfo
from collections import defaultdict
from dataclasses import dataclass

from django.utils import timezone

from apps.alerts.models import Notification
from apps.alerts.rules import current as current_rule
from apps.tenancy import context
from apps.tenancy.models import Agency

MISSING_ACTUALS_DAYS = 3  # "3 days before cutoff" (P11.2)
DELAY_WINDOW_DAYS = 14  # delay alerts look at months locked this recently


@dataclass(frozen=True)
class Message:
    type: str
    title: str
    body: str
    link: str
    key: str  # dedupe key without the recipient


def send(message: Message, user_ids) -> int:
    """Create one notification per recipient; returns how many were new."""
    ids = sorted({str(u) for u in user_ids if u})
    if not ids:
        return 0
    keys = {f"{message.key}:{u}" for u in ids}
    existing = set(Notification.objects.filter(dedupe_key__in=keys).values_list("dedupe_key", flat=True))
    rows = [
        Notification(
            user_id=u,
            type=message.type,
            title=message.title[:200],
            body=message.body,
            link=message.link[:500],
            dedupe_key=f"{message.key}:{u}"[:300],
        )
        for u in ids
        if f"{message.key}:{u}" not in existing
    ]
    Notification.objects.bulk_create(rows, ignore_conflicts=True)
    return len(rows)


# ---- Recipients ---------------------------------------------------------------------------------


class Directory:
    """Role assignments of the agency's active users, loaded once per scan or event."""

    def __init__(self):
        from apps.accounts.models import RoleAssignment
        from apps.structure.models import Office

        self.offices = {o.id: o for o in Office.objects.all()}
        self.by_office = defaultdict(list)  # office id -> [(user id, level)]
        for user_id, office_id, level in RoleAssignment.objects.filter(user__is_active=True).values_list(
            "user_id", "office_id", "level"
        ):
            self.by_office[office_id].append((user_id, level))
        self.root = next((o for o in self.offices.values() if o.parent_id is None), None)

    def _chain(self, office) -> list:
        """The office and its ancestors, nearest first."""
        ids = [*office.ancestor_ids, str(office.id)]
        return [o for o in (self._get(i) for i in reversed(ids)) if o is not None]

    def _get(self, office_id):
        import uuid

        try:
            return self.offices.get(uuid.UUID(str(office_id)))
        except ValueError:
            return None

    def admins(self, office) -> set:
        for o in self._chain(office):
            found = {u for u, level in self.by_office[o.id] if level == "admin"}
            if found:
                return found
        return set()

    def agency_admins(self) -> set:
        return {u for u, level in self.by_office[self.root.id] if level == "admin"} if self.root else set()

    def users_up_the_tree(self, office) -> set:
        return {u for o in self._chain(office) for u, _ in self.by_office[o.id]}


# ---- Helpers ------------------------------------------------------------------------------------


def _tz(agency_id):
    agency = Agency.objects.get(pk=agency_id)
    try:
        return zoneinfo.ZoneInfo(agency.timezone)
    except (zoneinfo.ZoneInfoNotFoundError, ValueError):
        return datetime.UTC


def month_label(period) -> str:
    return period.start_date.strftime("%B %Y")


def report_link(period, office) -> str:
    return f"/reports?fy={period.fiscal_year_id}&office={office.id}&period={period.id}"


def dashboard_link(period, office=None) -> str:
    office_part = f"&office={office.id}" if office is not None else ""
    return f"/dashboard?fy={period.fiscal_year_id}&period={period.id}{office_part}"


def reporting_offices(fy) -> list:
    """Offices expected to submit: those owning an approved plan of the year (as the board)."""
    from apps.planning.models import Plan

    return [p.office for p in Plan.objects.select_related("office").filter(fiscal_year=fy, status="approved")]


def submitted_office_ids(period) -> set:
    from apps.reporting.models import OfficeSubmission

    return set(
        OfficeSubmission.objects.filter(period=period, status__in=["submitted", "locked"]).values_list(
            "office_id", flat=True
        )
    )


# ---- The daily scan -----------------------------------------------------------------------------


def scan(now=None) -> dict:
    """Run every scheduled trigger for the current agency. Idempotent (dedupe keys)."""
    from apps.planning.models import FiscalYear, ReportingPeriod

    now = now or timezone.now()
    agency_id = context.require_agency_id()
    tz = _tz(agency_id)
    today = now.astimezone(tz).date()
    rule = current_rule()
    directory = Directory()
    counts = defaultdict(int)
    for fy in FiscalYear.objects.filter(status=FiscalYear.Status.OPEN):
        offices = reporting_offices(fy)
        for period in fy.periods.filter(status=ReportingPeriod.Status.OPEN).order_by("month_index"):
            days_left = (period.cutoff_at.astimezone(tz).date() - today).days
            if period.cutoff_at > now:
                if days_left in rule.remind_days_before:
                    counts["cutoff_reminder"] += _reminders(period, offices, days_left, directory)
                if days_left == MISSING_ACTUALS_DAYS:
                    counts["missing_actuals"] += _missing_actuals(period, directory)
            else:
                counts["cutoff_passed"] += _cutoff_passed(period, offices, directory)
        counts["delayed"] += _delays(fy, rule, now, directory)
    return dict(counts)


def _reminders(period, offices, days_left, directory) -> int:
    done = submitted_office_ids(period)
    sent = 0
    when = "today" if days_left == 0 else ("tomorrow" if days_left == 1 else f"in {days_left} days")
    for office in offices:
        if office.id in done:
            continue
        sent += send(
            Message(
                type=Notification.Type.CUTOFF_REMINDER,
                title=f"{office.code}: {month_label(period)} report due {when}",
                body=f"The cutoff for {month_label(period)} is {when}. {office.name} has not submitted yet.",
                link=report_link(period, office),
                key=f"cutoff-reminder:{period.id}:{office.id}:{days_left}",
            ),
            directory.admins(office),
        )
    return sent


def _cutoff_passed(period, offices, directory) -> int:
    done = submitted_office_ids(period)
    sent = 0
    for office in offices:
        if office.id in done:
            continue
        sent += send(
            Message(
                type=Notification.Type.CUTOFF_PASSED,
                title=f"{office.code}: {month_label(period)} report is late",
                body=f"The cutoff for {month_label(period)} has passed and {office.name} has not submitted.",
                link=report_link(period, office),
                key=f"cutoff-passed:{period.id}:{office.id}",
            ),
            directory.admins(office) | directory.agency_admins(),
        )
    return sent


def _missing_actuals(period, directory) -> int:
    """Activities with a target this month and no accomplishment, grouped per office to tell."""
    from apps.planning.models import ActivityTarget
    from apps.reporting.models import ActivityActual

    targets = (
        ActivityTarget.objects.filter(
            period=period, planned_qty__gt=0, activity__plan__status="approved", activity__row_kind="activity"
        )
        .select_related("activity__plan__office", "activity__implementing_office")
        .order_by("activity__plan__office__path", "activity__sort_order")
    )
    reported = set(ActivityActual.objects.filter(period=period).values_list("activity_lineage_id", flat=True))
    per_office = defaultdict(list)  # office -> [activity]
    for t in targets:
        act = t.activity
        if act.lineage_id in reported:
            continue
        per_office[act.plan.office].append(act)
        if act.implementing_office_id and act.implementing_office_id != act.plan.office_id:
            per_office[act.implementing_office].append(act)
    sent = 0
    for office, acts in per_office.items():
        names = ", ".join(a.code or a.title[:40] for a in acts[:5]) + (" …" if len(acts) > 5 else "")
        sent += send(
            Message(
                type=Notification.Type.MISSING_ACTUALS,
                title=f"{office.code}: {len(acts)} activit{'y has' if len(acts) == 1 else 'ies have'} "
                f"no accomplishment for {month_label(period)}",
                body=f"The cutoff is in {MISSING_ACTUALS_DAYS} days. Still missing: {names}.",
                link=report_link(period, office),
                key=f"missing-actuals:{period.id}:{office.id}",
            ),
            directory.admins(office),
        )
    return sent


def _delays(fy, rule, now, directory) -> int:
    """After a month is locked: offices whose cumulative variance is below −threshold."""
    from apps.planning.models import ReportingPeriod
    from apps.results.agency import OWNER
    from apps.results.models import PeriodResult

    period = (
        fy.periods.filter(
            status=ReportingPeriod.Status.LOCKED,
            locked_at__gte=now - datetime.timedelta(days=DELAY_WINDOW_DAYS),
        )
        .order_by("-month_index")
        .first()
    )
    if period is None:
        return 0
    sent = 0
    rows = PeriodResult.objects.filter(
        period=period, view=OWNER, variance__lt=-rule.delay_threshold
    ).select_related("office")
    for row in rows.order_by("office__path"):
        points = abs(row.variance) * 100
        sent += send(
            Message(
                type=Notification.Type.DELAYED,
                title=f"{row.office.code} is {points:.2f} points behind plan ({month_label(period)})",
                body=f"{row.office.name}: cumulative accomplishment {row.cum_actual * 100:.2f}% against "
                f"a plan of {row.cum_plan * 100:.2f}% at the end of {month_label(period)} "
                f"({row.status_label}).",
                link=dashboard_link(period, row.office),
                key=f"delayed:{period.id}:{row.office_id}",
            ),
            directory.users_up_the_tree(row.office),
        )
    return sent


# ---- Events (called by the services that cause them) --------------------------------------------


def submission_returned(submission) -> int:
    period, office = submission.period, submission.office
    note = f" Note: {submission.return_note}" if submission.return_note else ""
    stamp = submission.returned_at.isoformat() if submission.returned_at else ""
    return send(
        Message(
            type=Notification.Type.SUBMISSION_RETURNED,
            title=f"{office.code}: {month_label(period)} report returned",
            body=f"The {month_label(period)} report of {office.name} was returned for changes.{note}",
            link=report_link(period, office),
            key=f"returned:{submission.id}:{stamp}",
        ),
        Directory().admins(office),
    )


def period_locked(period, *, unlocked: bool = False, reason: str = "") -> int:
    """Admins of every office that reports (owns an approved plan) in the period's year."""
    directory = Directory()
    users = set()
    for office in reporting_offices(period.fiscal_year):
        users |= directory.admins(office)
    stamp = (
        timezone.now().isoformat() if unlocked else (period.locked_at.isoformat() if period.locked_at else "")
    )
    if unlocked:
        message = Message(
            type=Notification.Type.PERIOD_UNLOCKED,
            title=f"{month_label(period)} was reopened",
            body=f"{month_label(period)} is open again for corrections."
            + (f" Reason: {reason}" if reason else ""),
            link=dashboard_link(period),
            key=f"unlocked:{period.id}:{stamp}",
        )
    else:
        message = Message(
            type=Notification.Type.PERIOD_LOCKED,
            title=f"{month_label(period)} is locked",
            body=f"The results for {month_label(period)} are now final.",
            link=dashboard_link(period),
            key=f"locked:{period.id}:{stamp}",
        )
    return send(message, users)


def plan_submitted(plan) -> int:
    stamp = plan.submitted_at.isoformat() if plan.submitted_at else ""
    return send(
        Message(
            type=Notification.Type.PLAN_SUBMITTED,
            title=f"{plan.office.code}: plan {plan.fiscal_year.label} v{plan.version} waits for approval",
            body=f"{plan.office.name} submitted its {plan.fiscal_year.label} plan (version {plan.version}).",
            link="/plans/approvals",
            key=f"plan-submitted:{plan.id}:{stamp}",
        ),
        Directory().agency_admins(),
    )

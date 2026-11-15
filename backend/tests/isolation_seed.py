"""Rows in every tenant table for two agencies, used by the isolation tests (P1.9, P14.2).

When a phase adds a tenant table, add a builder to ``BUILDERS``: the isolation test fails for any
tenant table that has no rows in both agencies.
"""

from datetime import timedelta

from django.utils import timezone

from apps.tenancy import context
from apps.tenancy.models import PlatformAdmin, SupportGrant
from tests.factories import assign, make_agency, make_office, make_root, make_user


def _base(code):
    agency = make_agency(code)
    root = make_root(agency)
    child = make_office(root, f"{code.upper()}-1")
    user = make_user(agency, f"admin@{code}.gov")
    assign(user, root, "admin")
    return {"agency": agency, "root": root, "child": child, "user": user}


def _support_grant(objs, platform_admin):
    with context.agency_context(objs["agency"].id):
        SupportGrant.objects.create(
            platform_admin_id=platform_admin.id,
            granted_by=objs["user"],
            reason="isolation test",
            expires_at=timezone.now() + timedelta(hours=1),
        )


def _group(objs, shared):
    from apps.structure.models import OfficeGroup, OfficeGroupMember

    with context.agency_context(objs["agency"].id):
        group = OfficeGroup.objects.create(name="Group")
        OfficeGroupMember.objects.create(group=group, office=objs["child"])


def _audit(objs, shared):
    from apps.audit.models import AuditLog

    with context.agency_context(objs["agency"].id):
        AuditLog.objects.create(agency_id=objs["agency"].id, actor_type="system", action="seed")


def _planning(objs, shared):
    from apps.planning.models import Activity, ActivityTarget, Indicator, IndicatorTarget, Plan
    from apps.planning.services import create_fiscal_year

    with context.agency_context(objs["agency"].id):
        fy = create_fiscal_year("2026", 2026)
        period = fy.periods.get(month_index=1)
        plan = Plan.objects.create(office=objs["child"], fiscal_year=fy)
        act = Activity.objects.create(
            plan=plan,
            row_kind="activity",
            title="Do things",
            measure_type="quantity",
            annual_target=1,
            total_cost=1,
        )
        ActivityTarget.objects.create(activity=act, period=period, planned_qty=1)
        ind = Indicator.objects.create(plan=plan, name="Things done", annual_target=1)
        IndicatorTarget.objects.create(indicator=ind, period=period, planned_value=1)
        objs.update(fy=fy, plan=plan, activity=act, indicator=ind, period=period)


def _reporting(objs, shared):
    from apps.reporting.models import ActivityActual, Attachment, IndicatorActual, OfficeSubmission

    with context.agency_context(objs["agency"].id):
        office, period = objs["child"], objs["period"]
        OfficeSubmission.objects.create(office=office, period=period)
        actual = ActivityActual.objects.create(
            activity_lineage_id=objs["activity"].lineage_id, period=period, office=office, actual_qty=1
        )
        IndicatorActual.objects.create(
            indicator_lineage_id=objs["indicator"].lineage_id, period=period, office=office, actual_value=1
        )
        Attachment.objects.create(
            target_type="activity_actual",
            target_id=actual.id,
            office=office,
            period=period,
            file_name="a.pdf",
            content_type="application/pdf",
            size_bytes=1,
            sha256="0" * 64,
            storage_key="k",
        )


def _results(objs, shared):
    from apps.results.models import PeriodResult

    with context.agency_context(objs["agency"].id):
        PeriodResult.objects.create(
            period=objs["period"],
            office=objs["child"],
            view="owner",
            periodic_plan=0,
            periodic_actual=0,
            cum_plan=0,
            cum_actual=0,
            variance=0,
            status_label="ON-TIME",
            funds_total=0,
            funds_used_est=0,
        )


def _jobs(objs, shared):
    from apps.jobs.models import Job

    with context.agency_context(objs["agency"].id):
        Job.objects.create(kind="alert_scan")


def _export_template(objs, shared):
    from apps.exports.models import ExportTemplate

    with context.agency_context(objs["agency"].id):
        ExportTemplate.objects.create(
            agency_id=objs["agency"].id, kind="pptx", name="Agency", is_default=True, settings={}
        )


def _alerts(objs, shared):
    from apps.alerts.models import AlertRule, Notification

    with context.agency_context(objs["agency"].id):
        AlertRule.objects.create()
        Notification.objects.create(
            user=objs["user"],
            type="cutoff_reminder",
            title="Reminder",
            dedupe_key=f"seed:{objs['agency'].code}",
        )


# table name -> builder(objs, shared). Tables filled by _base are listed with None.
BUILDERS = {
    "agency": None,
    "user": None,
    "role_assignment": None,
    "org_level": None,
    "office": None,
    "support_grant": lambda objs, shared: _support_grant(objs, shared["platform_admin"]),
    "office_group": _group,
    "office_group_member": None,  # filled by _group
    "audit_log": _audit,
    "fiscal_year": _planning,
    "reporting_period": None,  # filled by _planning
    "scoring_profile": None,
    "plan": None,
    "activity": None,
    "activity_target": None,
    "indicator": None,
    "indicator_target": None,
    "office_submission": _reporting,
    "activity_actual": None,  # filled by _reporting
    "indicator_actual": None,
    "attachment": None,
    "period_result": _results,
    "job": _jobs,
    "export_template": _export_template,
    "alert_rule": _alerts,
    "notification": None,  # filled by _alerts
}


def seed_two_agencies():
    admin = PlatformAdmin(email="iso@vendor.example")
    admin.set_password("isolation-test-password")
    admin.save(using="owner")
    shared = {"platform_admin": admin}
    out = {}
    for code in ("iso-a", "iso-b"):
        objs = _base(code)
        for builder in BUILDERS.values():
            if builder:
                builder(objs, shared)
        out[code] = objs
    return out["iso-a"], out["iso-b"]

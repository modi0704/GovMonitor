"""Guided steps for the monitoring administrator: where the agency is in the yearly routine.

GET progress[?fiscal_year=&period=] — the six steps (offices, year, plans, monthly results, review,
report), whether each is done, and the per-office checklist for the plan and monthly steps. The
administrator enters everything on behalf of the offices; the steps only read what already exists.
"""

import zoneinfo
from datetime import date

from django.http import Http404
from django.utils import timezone
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts import permissions as perm
from apps.planning.models import FiscalYear, Plan, ReportingPeriod
from apps.reporting.models import OfficeSubmission
from apps.structure.models import Office
from apps.structure.ordering import tree_key
from apps.tenancy.models import Agency

DONE_REPORT = (OfficeSubmission.Status.SUBMITTED, OfficeSubmission.Status.LOCKED)


def _today(agency: Agency) -> date:
    try:
        return timezone.now().astimezone(zoneinfo.ZoneInfo(agency.timezone)).date()
    except Exception:  # noqa: BLE001 — an unknown zone falls back to UTC
        return timezone.now().date()


def default_period(periods: list, today: date):
    """The month to work on: the earliest open month that has started, else the latest started
    month, else the first month."""
    started = [p for p in periods if p.start_date <= today]
    open_started = [p for p in started if p.status == ReportingPeriod.Status.OPEN]
    if open_started:
        return open_started[0]
    if started:
        return started[-1]
    return periods[0] if periods else None


def _office(o: Office) -> dict:
    return {"id": str(o.id), "code": o.code, "name": o.name, "depth": o.depth}


class ProgressView(APIView):
    """GET ``?fiscal_year=&period=`` — the six guided steps, which are done, and the per-office checklist
    of plans and of the chosen month (agency administrator)."""

    permission_classes = [perm.IsAgencyAdmin]

    def get(self, request):
        q = request.query_params
        agency = Agency.objects.get(pk=request.user.agency_id)
        years = list(FiscalYear.objects.order_by("-start_date"))
        fy = None
        if q.get("fiscal_year"):
            fy = next((y for y in years if str(y.id) == q["fiscal_year"]), None)
            if fy is None:
                raise Http404()
        else:
            fy = next((y for y in years if y.status == FiscalYear.Status.OPEN), None) or (
                years[0] if years else None
            )

        offices = list(Office.objects.filter(is_active=True))
        by_id = {str(o.id): o for o in offices}
        offices.sort(key=lambda o: tree_key(o, by_id))
        root = next((o for o in offices if o.parent_id is None), None)
        parents = {o.parent_id for o in offices if o.parent_id}
        sub_offices = [o for o in offices if o.parent_id is not None]

        plans: dict = {}
        periods: list = []
        if fy is not None:
            for p in Plan.objects.filter(fiscal_year=fy).exclude(status=Plan.Status.SUPERSEDED):
                # An approved plan wins over a newer draft revision of it.
                if p.office_id not in plans or p.status == Plan.Status.APPROVED:
                    plans[p.office_id] = p
            periods = list(fy.periods.order_by("month_index"))
        # Offices that need their own plan: the lowest offices, plus any office that already has one.
        # A lowest office that only carries out activities of another office's plan is covered by it.
        covered: dict = {}
        if plans:
            from apps.planning.models import Activity

            for impl, owner in Activity.objects.filter(
                plan__in=list(plans.values()), implementing_office__isnull=False
            ).values_list("implementing_office_id", "plan__office__code"):
                covered.setdefault(impl, owner)
        planned = [o for o in offices if (o.id not in parents and o.id not in covered) or o.id in plans]
        counts = {}
        if plans:
            from django.db.models import Count, Q

            counts = {
                row["id"]: row
                for row in Plan.objects.filter(pk__in=[p.pk for p in plans.values()])
                .values("id")
                .annotate(
                    activities=Count("rows", filter=Q(rows__row_kind="activity"), distinct=True),
                    indicators=Count("indicators", distinct=True),
                )
            }
        plan_rows = []
        for o in planned:
            p = plans.get(o.id)
            c = counts.get(p.pk, {}) if p else {}
            plan_rows.append(
                {
                    "office": _office(o),
                    "plan_id": str(p.id) if p else None,
                    "status": p.status if p else "none",
                    "activities": c.get("activities", 0),
                    "indicators": c.get("indicators", 0),
                    "budget": str(p.approved_budget) if p and p.approved_budget is not None else None,
                }
            )
        plans_done = bool(plan_rows) and all(r["status"] == Plan.Status.APPROVED for r in plan_rows)
        plans_started = any(r["status"] != "none" for r in plan_rows)

        period = None
        if q.get("period"):
            period = next((p for p in periods if str(p.id) == q["period"]), None)
            if period is None:
                raise Http404()
        else:
            period = default_period(periods, _today(agency))

        month_rows = []
        months = []
        if period is not None:
            approved = {oid for oid, p in plans.items() if p.status == Plan.Status.APPROVED}
            by_period: dict = {}
            for s in OfficeSubmission.objects.filter(period__fiscal_year=fy, office_id__in=approved):
                by_period.setdefault(s.period_id, {})[s.office_id] = s.status
            for p in periods:
                done = sum(1 for st in by_period.get(p.id, {}).values() if st in DONE_REPORT)
                months.append(
                    {
                        "id": str(p.id),
                        "month_index": p.month_index,
                        "start_date": p.start_date.isoformat(),
                        "status": p.status,
                        "offices_done": done,
                        "offices_total": len(approved),
                    }
                )
            subs = by_period.get(period.id, {})
            for o in planned:
                if o.id in approved:
                    month_rows.append({"office": _office(o), "status": subs.get(o.id, "not_started")})
        month_done = bool(month_rows) and all(r["status"] in DONE_REPORT for r in month_rows)
        month_closed = period is not None and period.status == ReportingPeriod.Status.LOCKED

        steps = [
            {"key": "offices", "done": bool(sub_offices) or bool(agency.settings.get("setup_complete"))},
            {"key": "year", "done": fy is not None},
            {"key": "plans", "done": plans_done, "started": plans_started},
            {
                "key": "results",
                "done": month_done,
                "started": any(r["status"] != "not_started" for r in month_rows),
            },
            {"key": "review", "done": month_closed},
            {"key": "report", "done": False},
        ]
        current = next((s["key"] for s in steps if not s["done"]), "report")
        return Response(
            {
                "steps": steps,
                "current": current,
                "offices_count": len(sub_offices),
                "root": _office(root) if root else None,
                "fiscal_years": [{"id": str(y.id), "label": y.label, "status": y.status} for y in years],
                "fiscal_year": {"id": str(fy.id), "label": fy.label, "status": fy.status} if fy else None,
                "plans": plan_rows,
                "period": (
                    {
                        "id": str(period.id),
                        "month_index": period.month_index,
                        "start_date": period.start_date.isoformat(),
                        "status": period.status,
                    }
                    if period
                    else None
                ),
                "months": months,
                "monthly": month_rows,
            }
        )

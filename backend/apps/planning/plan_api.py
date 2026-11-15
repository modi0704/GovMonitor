"""Plans API (MASTERPLAN 13: plans — bulk save, submit, approve, revise, compare; P5.3–P5.9).

Every plan is office-bound: reads need ``can_view`` on the plan's office, edits ``can_edit``;
approving, returning and setting the approved budget are for the agency administrator.
"""

from decimal import Decimal

from django.db.models import Sum
from django.http import Http404
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts import permissions as perm
from apps.audit import services as audit
from apps.audit.services import jsonable
from apps.planning import plans as svc
from apps.planning.api import planning_error
from apps.planning.models import FiscalYear, Plan
from apps.planning.numbers import plain
from apps.planning.services import PlanningError
from apps.planning.validation import validate_plan


def plan_summary(plan: Plan, user=None) -> dict:
    planned_cost = plan.rows.filter(row_kind="activity").aggregate(s=Sum("total_cost"))["s"] or Decimal(0)
    return {
        "id": str(plan.id),
        "office": {"id": str(plan.office_id), "code": plan.office.code, "name": plan.office.name},
        "fiscal_year": {"id": str(plan.fiscal_year_id), "label": plan.fiscal_year.label},
        "version": plan.version,
        "status": plan.status,
        "approved_budget": jsonable(plan.approved_budget),
        "planned_cost": jsonable(planned_cost),
        "submitted_at": plan.submitted_at.isoformat() if plan.submitted_at else None,
        "submitted_by": plan.submitted_by.email if plan.submitted_by_id else None,
        "approved_at": plan.approved_at.isoformat() if plan.approved_at else None,
        "approved_by": plan.approved_by.email if plan.approved_by_id else None,
        "updated_at": plan.updated_at.isoformat(),
        "can_edit": bool(user) and perm.can_edit(user, plan.office) and plan.status == Plan.Status.DRAFT,
        "office_editable": bool(user) and perm.can_edit(user, plan.office),
    }


def _targets(row) -> tuple[list, list]:
    qty, amounts = ["0"] * 12, [None] * 12
    for t in row.targets.all():
        qty[t.period.month_index - 1] = plain(t.planned_qty)
        amounts[t.period.month_index - 1] = jsonable(t.planned_amount)
    return qty, amounts


def plan_detail(plan: Plan, user) -> dict:
    data = plan_summary(plan, user)
    data["notes"] = plan.notes
    data["weighting"] = plan.fiscal_year.profile.weighting
    data["periods"] = [
        {"month_index": p.month_index, "start_date": p.start_date.isoformat(), "status": p.status}
        for p in plan.fiscal_year.periods.order_by("month_index")
    ]
    rows = []
    for r in (
        plan.rows.select_related("implementing_office")
        .prefetch_related("targets__period")
        .order_by("sort_order")
    ):
        qty, amounts = _targets(r)
        rows.append(
            {
                "id": str(r.id),
                "lineage_id": str(r.lineage_id),
                "parent": str(r.parent_id) if r.parent_id else None,
                "row_kind": r.row_kind,
                "code": r.code,
                "title": r.title,
                "sort_order": r.sort_order,
                "measure_type": r.measure_type,
                "unit": r.unit,
                "annual_target": jsonable(r.annual_target),
                "unit_cost": jsonable(r.unit_cost),
                "total_cost": jsonable(r.total_cost),
                "manual_weight": jsonable(r.manual_weight),
                "implementing_office_id": str(r.implementing_office_id) if r.implementing_office_id else None,
                "targets": qty,
                "amounts": amounts,
            }
        )
    data["rows"] = rows
    data["indicators"] = []
    for ind in plan.indicators.prefetch_related("targets__period").order_by("sort_order"):
        values = ["0"] * 12
        for t in ind.targets.all():
            values[t.period.month_index - 1] = plain(t.planned_value)
        data["indicators"].append(
            {
                "id": str(ind.id),
                "lineage_id": str(ind.lineage_id),
                "code": ind.code,
                "name": ind.name,
                "kind": ind.kind,
                "unit": ind.unit,
                "annual_target": jsonable(ind.annual_target),
                "weight": jsonable(ind.weight),
                "aggregation": ind.aggregation,
                "sort_order": ind.sort_order,
                "targets": values,
            }
        )
    data["issues"] = validate_plan(plan, for_submit=False)
    return data


def get_plan(request, plan_id, *, edit=False) -> Plan:
    qs = perm.filter_by_scope(
        Plan.objects.select_related("office", "fiscal_year__profile", "submitted_by", "approved_by"),
        request.user,
        edit=edit,
    )
    plan = qs.filter(pk=plan_id).first()
    if plan is None:
        raise Http404()
    return plan


class PlanListView(APIView):
    """GET plans in scope (filters: fiscal_year, office, status); POST create a draft."""

    def get(self, request):
        qs = perm.filter_by_scope(
            Plan.objects.select_related("office", "fiscal_year", "submitted_by", "approved_by"), request.user
        )
        p = request.query_params
        try:
            if p.get("fiscal_year"):
                qs = qs.filter(fiscal_year_id=p["fiscal_year"])
            if p.get("office"):
                qs = qs.filter(office_id=p["office"])
            if p.get("status"):
                qs = qs.filter(status__in=p["status"].split(","))
            rows = [plan_summary(plan, request.user) for plan in qs.order_by("office__path", "-version")]
        except Exception as exc:  # noqa: BLE001 — malformed ids
            raise Http404() from exc
        return Response(rows)

    def post(self, request):
        office = perm.get_office_or_404(request.user, request.data.get("office_id"), edit=True)
        fy_id = request.data.get("fiscal_year_id")
        if not fy_id:
            return Response({"fiscal_year_id": ["Choose a fiscal year."]}, status=400)
        fy = FiscalYear.objects.filter(pk=fy_id).first()
        if fy is None:  # unknown, or another agency's (P14.2): never say which
            raise Http404("No such fiscal year.")
        try:
            plan = svc.create_draft(office, fy)
        except PlanningError as err:
            return planning_error(err)
        return Response(plan_detail(plan, request.user), status=status.HTTP_201_CREATED)


class PlanDetailView(APIView):
    def get(self, request, plan_id):
        return Response(plan_detail(get_plan(request, plan_id), request.user))

    def patch(self, request, plan_id):
        """Approved budget (agency administrator) — allowed in any status (P5.8)."""
        plan = get_plan(request, plan_id)
        if "approved_budget" in request.data:
            if not perm.is_agency_admin(request.user):
                return Response(
                    {"detail": "Only the agency administrator sets the approved budget."}, status=403
                )
            try:
                svc.set_approved_budget(plan, request.data["approved_budget"])
            except PlanningError as err:
                return planning_error(err)
        return Response(plan_summary(plan, request.user))


class PlanSaveView(APIView):
    """Bulk save from the grid: all changed rows and indicators in one request."""

    def post(self, request, plan_id):
        plan = get_plan(request, plan_id, edit=True)
        try:
            keymap = svc.bulk_save(plan, request.data)
        except PlanningError as err:
            return planning_error(err)
        plan.refresh_from_db()
        return Response({"plan": plan_detail(plan, request.user), "created": keymap})


class PlanSubmitView(APIView):
    def post(self, request, plan_id):
        plan = get_plan(request, plan_id, edit=True)
        try:
            svc.submit(plan, request.user)
        except PlanningError as err:
            return planning_error(err)
        return Response(plan_detail(plan, request.user))


class PlanApproveView(APIView):
    permission_classes = [perm.IsAgencyAdmin]

    def post(self, request, plan_id):
        plan = get_plan(request, plan_id)
        try:
            svc.approve(plan, request.user)
        except PlanningError as err:
            return planning_error(err)
        return Response(plan_detail(plan, request.user))


class PlanReturnView(APIView):
    permission_classes = [perm.IsAgencyAdmin]

    def post(self, request, plan_id):
        plan = get_plan(request, plan_id)
        try:
            svc.return_to_draft(plan, request.user, str(request.data.get("note", ""))[:2000])
        except PlanningError as err:
            return planning_error(err)
        return Response(plan_detail(plan, request.user))


class PlanReviseView(APIView):
    def post(self, request, plan_id):
        plan = get_plan(request, plan_id, edit=True)
        try:
            new = svc.revise(plan)
        except PlanningError as err:
            return planning_error(err)
        return Response(plan_detail(new, request.user), status=status.HTTP_201_CREATED)


class PlanVersionsView(APIView):
    def get(self, request, plan_id):
        plan = get_plan(request, plan_id)
        versions = Plan.objects.select_related("office", "fiscal_year", "submitted_by", "approved_by").filter(
            office=plan.office, fiscal_year=plan.fiscal_year
        )
        return Response([plan_summary(v, request.user) for v in versions.order_by("-version")])


class PlanCompareView(APIView):
    """Compare this version with another version of the same office's plan (``?with=<plan id>``)."""

    def get(self, request, plan_id):
        plan = get_plan(request, plan_id)
        other = get_plan(request, request.query_params.get("with"))
        if (other.office_id, other.fiscal_year_id) != (plan.office_id, plan.fiscal_year_id):
            return Response({"detail": "Only versions of the same plan can be compared."}, status=400)
        old, new = sorted([plan, other], key=lambda p: p.version)
        return Response(svc.compare(old, new))


class PlanCopyView(APIView):
    """Copy a plan into another fiscal year as a draft — targets kept, actuals not (P5.9)."""

    def post(self, request, plan_id):
        plan = get_plan(request, plan_id, edit=True)
        fy = (
            FiscalYear.objects.filter(pk=request.data.get("fiscal_year_id")).first()
            if request.data.get("fiscal_year_id")
            else None
        )
        if fy is None or fy.pk == plan.fiscal_year_id:
            return Response({"fiscal_year_id": ["Choose another fiscal year."]}, status=400)
        if Plan.objects.filter(office=plan.office, fiscal_year=fy).exists():
            return planning_error(
                PlanningError("plan_exists", "This office already has a plan for that year.")
            )
        new = svc.clone(plan, fiscal_year=fy, keep_lineage=False)
        audit.record(
            "copy",
            new,
            after={"from_plan": str(plan.id), "from_year": plan.fiscal_year.label},
            office_id=plan.office_id,
        )
        return Response(plan_detail(new, request.user), status=status.HTTP_201_CREATED)

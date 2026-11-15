"""Monthly reporting API (MASTERPLAN 13: periods, submissions — bulk save, submit, return; P6.3–P6.8).

GET  reports?office&period[&view=implementing]   one office's month
POST reports/save      bulk save of actuals, remarks, delay reasons, amounts
POST reports/preview   live result for unsaved numbers (engine call)
POST reports/submit    office submits its month
POST reports/return    agency administrator returns it with a note
"""

from decimal import Decimal, InvalidOperation
from uuid import UUID

from django.db import transaction
from django.http import Http404
from django.utils import timezone
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts import permissions as perm
from apps.audit import services as audit
from apps.audit.services import jsonable
from apps.planning.models import ReportingPeriod
from apps.planning.numbers import plain
from apps.reporting import rules
from apps.reporting.models import ActivityActual, Attachment, IndicatorActual, OfficeSubmission
from apps.results import services as results
from apps.scoring import engine
from apps.structure.models import Office


def error(err: rules.ReportingError) -> Response:
    return Response({"detail": err.message, "code": err.code, **err.extra}, status=err.http)


def _dec(value, field, allow_none=False):
    if value is None or value == "":
        return None if allow_none else Decimal(0)
    try:
        d = Decimal(str(value).replace(",", ""))
    except InvalidOperation as exc:
        raise rules.ReportingError("bad_number", f"{field}: '{value}' is not a number.") from exc
    if not d.is_finite() or d < 0:
        raise rules.ReportingError("bad_number", f"{field}: enter zero or a positive number.")
    return d


def _context(request, office_id, period_id, *, view="owner"):
    period = (
        ReportingPeriod.objects.select_related("fiscal_year__profile").filter(pk=period_id).first()
        if (period_id)
        else None
    )
    if period is None:
        raise Http404()
    office = perm.get_office_or_404(request.user, office_id)
    return office, period


def _submission_payload(sub: OfficeSubmission | None) -> dict:
    if sub is None:
        return {"status": "draft"}
    return {
        "status": sub.status,
        "submitted_at": sub.submitted_at.isoformat() if sub.submitted_at else None,
        "submitted_by": sub.submitted_by.email if sub.submitted_by_id else None,
        "returned_at": sub.returned_at.isoformat() if sub.returned_at else None,
        "returned_by": sub.returned_by.email if sub.returned_by_id else None,
        "return_note": sub.return_note,
    }


def _rows_for(view, office, period):
    """(activity rows, owner plan or None) for the owner or the implementing view."""
    if view == "implementing":
        return results.implementing_activities(office, period.fiscal_year), None
    plan = rules.approved_plan(office, period.fiscal_year)
    return (results.plan_activities(plan) if plan else []), plan


def month_view(request, office: Office, period: ReportingPeriod, view: str) -> dict:
    m = period.month_index
    profile = period.fiscal_year.profile
    rows, plan = _rows_for(view, office, period)
    actuals = results.load_activity_actuals(period.fiscal_year, [r.lineage_id for r in rows])
    inputs = [results.activity_input(r, actuals) for r in rows]
    eng = profile.to_engine()
    attachments = _attachment_counts(period, [a for by_month in actuals.values() for a in by_month.values()])
    subs = {
        s.office_id: s
        for s in OfficeSubmission.objects.select_related("submitted_by", "returned_by").filter(
            period=period, office_id__in={r.plan.office_id for r in rows} | {office.id}
        )
    }
    activities = []
    for row, inp in zip(rows, inputs, strict=True):
        rp, ra, no_target = engine.activity_progress(inp, eng.cap_at_100)
        this = actuals.get(row.lineage_id, {}).get(m)
        planned = list(inp.planned)
        prev_actual = sum((v or Decimal(0) for v in inp.actual[: m - 1]), Decimal(0))
        ref = rules.ActivityRef(row, row.plan)
        sub = subs.get(row.plan.office_id)
        editable = (
            rules.can_edit_activity(request.user, ref)
            and period.status == ReportingPeriod.Status.OPEN
            and (sub is None or sub.editable)
        )
        activities.append(
            {
                "lineage_id": str(row.lineage_id),
                "code": row.code,
                "title": row.title,
                "unit": row.unit,
                "measure_type": row.measure_type,
                "annual_target": plain(row.annual_target),
                "owner_office": {"id": str(row.plan.office_id), "code": row.plan.office.code},
                "implementing_office": {
                    "id": str(row.implementing_office_id or row.plan.office_id),
                    "code": (row.implementing_office or row.plan.office).code,
                },
                "target_month": plain(planned[m - 1]),
                "cum_target": plain(sum(planned[:m], Decimal(0))),
                "prev_cum_actual": plain(prev_actual),
                "actual": plain(this.actual_qty) if this else None,
                "actual_amount": jsonable(this.actual_amount) if this else None,
                "remarks": this.remarks if this else "",
                "delay_reason": this.delay_reason if this else "",
                "attachments": attachments.get(this.pk, 0) if this else 0,
                "planned_ratio": jsonable(rp[m - 1]),
                "actual_ratio": jsonable(ra[m - 1]),
                "behind": (not no_target) and ra[m - 1] < rp[m - 1],
                "no_target": no_target,
                "editable": editable,
            }
        )
    indicators = []
    if view == "owner" and plan:
        inds = list(plan.indicators.prefetch_related("targets__period").order_by("sort_order"))
        ind_actuals = results.load_indicator_actuals(period.fiscal_year, [i.lineage_id for i in inds])
        ind_files = _attachment_counts(
            period, [a for by in ind_actuals.values() for a in by.values()], "indicator_actual"
        )
        for ind in inds:
            this = ind_actuals.get(ind.lineage_id, {}).get(m)
            targets = {t.period.month_index: t.planned_value for t in ind.targets.all()}
            indicators.append(
                {
                    "lineage_id": str(ind.lineage_id),
                    "code": ind.code,
                    "name": ind.name,
                    "unit": ind.unit,
                    "annual_target": plain(ind.annual_target),
                    "aggregation": ind.aggregation,
                    "target_month": plain(targets.get(m, Decimal(0))),
                    "actual": plain(this.actual_value) if this and this.actual_value is not None else None,
                    "remarks": this.remarks if this else "",
                    "attachments": ind_files.get(this.pk, 0) if this else 0,
                }
            )
    result = (
        results.live_implementing_result(office, period.fiscal_year)
        if view == "implementing"
        else (results.live_plan_result(plan) if plan else None)
    )
    own_sub = subs.get(office.id)
    return {
        "office": {"id": str(office.id), "code": office.code, "name": office.name},
        "view": view,
        "has_plan": bool(rows),
        "plan_id": str(plan.id) if plan else None,
        "period": {
            "id": str(period.id),
            "month_index": m,
            "start_date": period.start_date.isoformat(),
            "cutoff_at": period.cutoff_at.isoformat(),
            "status": period.status,
            "fiscal_year": {"id": str(period.fiscal_year_id), "label": period.fiscal_year.label},
        },
        "submission": _submission_payload(own_sub),
        "can_submit": view == "owner"
        and plan is not None
        and perm.can_edit(request.user, office)
        and period.status == ReportingPeriod.Status.OPEN
        and (own_sub is None or own_sub.editable),
        "can_return": perm.is_agency_admin(request.user)
        and own_sub is not None
        and own_sub.status == "submitted",
        "mov_required": profile.mov_required,
        "show_amounts": profile.show_actual_amounts,
        "activities": activities,
        "indicators": indicators,
        "result": results.headline(result, m, eng),
    }


def _attachment_counts(period, actuals, target_type="activity_actual") -> dict:
    from django.db.models import Count

    ids = [a.pk for a in actuals]
    if not ids:
        return {}
    rows = (
        Attachment.objects.filter(target_type=target_type, target_id__in=ids, deleted_at=None)
        .values("target_id")
        .annotate(n=Count("id"))
    )
    return {r["target_id"]: r["n"] for r in rows}


class ReportView(APIView):
    def get(self, request):
        p = request.query_params
        view = "implementing" if p.get("view") == "implementing" else "owner"
        office, period = _context(request, p.get("office"), p.get("period"))
        return Response(month_view(request, office, period, view))


def _period(period_id) -> ReportingPeriod:
    period = (
        ReportingPeriod.objects.select_related("fiscal_year__profile").filter(pk=period_id).first()
        if (period_id)
        else None
    )
    if period is None:
        raise Http404()
    return period


@transaction.atomic
def save_actuals(user, period: ReportingPeriod, data: dict) -> int:
    """Apply the P6.4 rules row by row; all rows or none."""
    saved = 0
    for item in data.get("activities", []):
        ref = rules.activity_in_period(item.get("lineage_id"), period)
        if ref is None:
            raise rules.ReportingError(
                "not_found", "An activity being saved is not in an approved plan.", http=404
            )
        rules.check_can_report_activity(user, ref, period)
        actual = ActivityActual.objects.filter(
            activity_lineage_id=ref.activity.lineage_id, period=period
        ).first()
        actual = actual or ActivityActual(
            activity_lineage_id=ref.activity.lineage_id, period=period, office=ref.owner_office
        )
        if "actual" in item:
            actual.actual_qty = _dec(item["actual"], ref.activity.code or "actual")
        if "actual_amount" in item:
            actual.actual_amount = _dec(item["actual_amount"], "amount spent", allow_none=True)
        if "remarks" in item:
            actual.remarks = str(item["remarks"])[:4000]
        if "delay_reason" in item:
            actual.delay_reason = str(item["delay_reason"])[:4000]
        actual.entered_by = user
        actual.save()
        saved += 1
    for item in data.get("indicators", []):
        ind = rules.indicator_in_period(item.get("lineage_id"), period)
        if ind is None or not perm.can_view(user, ind.plan.office):
            raise rules.ReportingError(
                "not_found", "An indicator being saved is not in an approved plan.", http=404
            )
        if not perm.can_edit(user, ind.plan.office):
            raise rules.ReportingError("read_only", "You have read-only access to this office.", http=403)
        rules.check_period_open(period)
        rules.check_submission_editable(ind.plan.office, period)
        actual = IndicatorActual.objects.filter(indicator_lineage_id=ind.lineage_id, period=period).first()
        actual = actual or IndicatorActual(
            indicator_lineage_id=ind.lineage_id, period=period, office=ind.plan.office
        )
        if "actual" in item:
            actual.actual_value = _dec(item["actual"], ind.code or "indicator", allow_none=True)
        if "remarks" in item:
            actual.remarks = str(item["remarks"])[:4000]
        actual.entered_by = user
        actual.save()
        saved += 1
    return saved


class ReportSaveView(APIView):
    def post(self, request):
        office, period = _context(request, request.data.get("office"), request.data.get("period"))
        view = "implementing" if request.data.get("view") == "implementing" else "owner"
        try:
            save_actuals(request.user, period, request.data)
        except rules.ReportingError as err:
            return error(err)
        return Response(month_view(request, office, period, view))


class ReportPreviewView(APIView):
    """Live result for numbers typed but not saved yet (P6.5). Read-only (D29-style allow-list)."""

    def post(self, request):
        office, period = _context(request, request.data.get("office"), request.data.get("period"))
        view = "implementing" if request.data.get("view") == "implementing" else "owner"
        m = period.month_index
        overrides = {}
        for item in request.data.get("activities", []):
            try:
                lineage = UUID(str(item.get("lineage_id")))
                qty = _dec(item.get("actual"), "actual")
                amount = _dec(item.get("actual_amount"), "amount", allow_none=True)
            except (rules.ReportingError, ValueError):
                continue
            overrides[(lineage, m)] = (qty, amount)
        if view == "implementing":
            result = results.live_implementing_result(office, period.fiscal_year, overrides)
        else:
            plan = rules.approved_plan(office, period.fiscal_year)
            result = results.live_plan_result(plan, overrides) if plan else None
        return Response({"result": results.headline(result, m, period.fiscal_year.profile.to_engine())})


def submission_problems(office, period) -> list[dict]:
    """Rows that block submission: missing delay reasons (P6.5) and missing files (P6.6)."""
    plan = rules.approved_plan(office, period.fiscal_year)
    if plan is None:
        return [{"code": "no_plan", "message": "This office has no approved plan for the year.", "row": None}]
    m = period.month_index
    profile = period.fiscal_year.profile
    eng = profile.to_engine()
    rows = results.plan_activities(plan)
    actuals = results.load_activity_actuals(period.fiscal_year, [r.lineage_id for r in rows])
    files = _attachment_counts(period, [a for by in actuals.values() for a in by.values()])
    problems = []
    for row in rows:
        inp = results.activity_input(row, actuals)
        rp, ra, no_target = engine.activity_progress(inp, eng.cap_at_100)
        this = actuals.get(row.lineage_id, {}).get(m)
        label = row.code or row.title[:40]
        if not no_target and ra[m - 1] < rp[m - 1] and not (this and this.delay_reason.strip()):
            problems.append(
                {
                    "code": "delay_reason",
                    "row": str(row.lineage_id),
                    "message": f"{label}: behind plan — give the reason for the delay.",
                }
            )
        if profile.mov_required and this and this.actual_qty and not files.get(this.pk):
            problems.append(
                {
                    "code": "mov_required",
                    "row": str(row.lineage_id),
                    "message": f"{label}: attach at least one supporting file.",
                }
            )
    return problems


class ReportSubmitView(APIView):
    @transaction.atomic
    def post(self, request):
        office, period = _context(request, request.data.get("office"), request.data.get("period"))
        try:
            if not perm.can_edit(request.user, office):
                raise rules.ReportingError("read_only", "You have read-only access to this office.", http=403)
            rules.check_period_open(period)
            sub = rules.check_submission_editable(office, period)
            problems = submission_problems(office, period)
            if problems:
                raise rules.ReportingError(
                    "cannot_submit", f"Fix {len(problems)} problem(s) before submitting.", problems=problems
                )
        except rules.ReportingError as err:
            return error(err)
        sub.status = OfficeSubmission.Status.SUBMITTED
        sub.submitted_by = request.user
        sub.submitted_at = timezone.now()
        with audit.suppressed():
            sub.save()
        audit.record("submit", sub, after={"month": period.month_index}, office_id=office.id)
        return Response(month_view(request, office, period, "owner"))


class ReportReturnView(APIView):
    permission_classes = [perm.IsAgencyAdmin]

    @transaction.atomic
    def post(self, request):
        office, period = _context(request, request.data.get("office"), request.data.get("period"))
        note = str(request.data.get("note", "")).strip()
        if not note:
            return Response({"note": ["Say what needs correcting."]}, status=400)
        sub = OfficeSubmission.objects.filter(office=office, period=period).first()
        if sub is None or sub.status != OfficeSubmission.Status.SUBMITTED:
            return error(
                rules.ReportingError("not_submitted", "Only a submitted report can be returned.", http=409)
            )
        sub.status = OfficeSubmission.Status.RETURNED
        sub.returned_by = request.user
        sub.returned_at = timezone.now()
        sub.return_note = note[:4000]
        with audit.suppressed():
            sub.save()
        audit.record(
            "return", sub, after={"month": period.month_index, "note": sub.return_note}, office_id=office.id
        )
        return Response(month_view(request, office, period, "owner"))


class SubmissionBoardView(APIView):
    """GET ``?period=`` — every office with an approved plan × its submission status (P7.6)."""

    permission_classes = [perm.IsAgencyAdmin]

    def get(self, request):
        from apps.planning.models import Plan

        period = _period(request.query_params.get("period"))
        fy = period.fiscal_year
        plans = {
            p.office_id: p
            for p in Plan.objects.select_related("office").filter(fiscal_year=fy, status=Plan.Status.APPROVED)
        }
        subs = {
            s.office_id: s
            for s in OfficeSubmission.objects.select_related("submitted_by", "returned_by").filter(
                period=period
            )
        }
        now = timezone.now()
        rows = []
        for office in Office.objects.filter(pk__in=plans.keys()).order_by("path"):
            sub = subs.get(office.id)
            rows.append(
                {
                    "office": {
                        "id": str(office.id),
                        "code": office.code,
                        "name": office.name,
                        "depth": office.depth,
                    },
                    "plan_version": plans[office.id].version,
                    **_submission_payload(sub),
                }
            )
        periods = list(fy.periods.order_by("month_index"))
        locked = [p for p in periods if p.status == ReportingPeriod.Status.LOCKED]
        earlier_open = any(
            p.status == ReportingPeriod.Status.OPEN for p in periods if p.month_index < period.month_index
        )
        return Response(
            {
                "period": {
                    "id": str(period.id),
                    "month_index": period.month_index,
                    "start_date": period.start_date.isoformat(),
                    "cutoff_at": period.cutoff_at.isoformat(),
                    "status": period.status,
                    "locked_at": period.locked_at.isoformat() if period.locked_at else None,
                    "locked_by": period.locked_by.email if period.locked_by_id else None,
                    "days_to_cutoff": (period.cutoff_at - now).days
                    if period.cutoff_at > now
                    else -((now - period.cutoff_at).days),
                    "can_lock": period.status == ReportingPeriod.Status.OPEN and not earlier_open,
                    "can_unlock": bool(locked) and locked[-1].pk == period.pk,
                },
                "offices": rows,
                "not_submitted": [r["office"] for r in rows if r["status"] in ("draft", "returned")],
            }
        )

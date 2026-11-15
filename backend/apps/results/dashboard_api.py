"""Dashboard API (MASTERPLAN P8.1): everything one dashboard screen needs, in one call.

    GET dashboard?office&period[&view=owner|implementing]

Numbers come only from ``results.read`` (frozen when the month is locked, live otherwise).
"""

from decimal import Decimal

from django.http import Http404
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts import permissions as perm
from apps.audit.services import jsonable
from apps.planning.models import ReportingPeriod
from apps.planning.numbers import plain
from apps.results import read
from apps.results.agency import IMPLEMENTING, OWNER
from apps.structure.models import Office, OfficeGroupMember


def get_period(period_id) -> ReportingPeriod:
    period = None
    if period_id:
        try:
            period = (
                ReportingPeriod.objects.select_related("fiscal_year__profile", "locked_by")
                .filter(pk=period_id)
                .first()
            )
        except (ValueError, TypeError, Exception):  # noqa: BLE001 — malformed id
            period = None
    if period is None:
        raise Http404()
    return period


def office_ref(o: Office) -> dict:
    return {"id": str(o.id), "code": o.code, "name": o.name, "depth": o.depth, "is_active": o.is_active}


def summary(rv: read.ResultView | None) -> dict | None:
    if rv is None:
        return None
    return {
        "cum_plan": jsonable(rv.cum_plan),
        "cum_actual": jsonable(rv.cum_actual),
        "variance": jsonable(rv.variance),
        "status": rv.status_label,
        "status_kind": rv.status_kind,
        "funds_total": jsonable(rv.funds_total),
        "rank_sibling": rv.rank_sibling,
    }


def series(rv: read.ResultView, month: int) -> dict:
    plan = rv.series.get("cum_plan", [])
    actual = rv.series.get("cum_actual", [])
    # The actual curve stops at the selected month (P8.1).
    return {"cum_plan": plan, "cum_actual": [v if i < month else None for i, v in enumerate(actual)]}


def quarters(rv: read.ResultView, month: int, profile) -> list:
    """Fiscal-quarter summaries derived from the monthly series by the engine (D9, P8.6)."""
    from apps.scoring import engine

    plan, actual = rv.series.get("cum_plan"), rv.series.get("cum_actual")
    if not plan or not actual:
        return []
    return [
        jsonable(q)
        for q in engine.quarter_summaries(
            [Decimal(v) for v in plan], [Decimal(v) for v in actual], month, profile
        )
    ]


def ranking_rows(results: dict, offices: dict, rows: list[tuple[str, int | None, Decimal | None]]) -> list:
    out = []
    for office_id, rank, value in rows:
        office = offices.get(office_id)
        if office is None:
            continue
        rv = results.get((office_id, OWNER)) or results.get((office_id, IMPLEMENTING))
        out.append(
            {"office": office_ref(office), "rank": rank, "value": jsonable(value), "result": summary(rv)}
        )
    return out


def rank_set(results: dict, office_ids: list[str], profile, month: int, *, allow_implementing: bool) -> list:
    """Rank a set of offices with the engine (7.8): same rule as the frozen ranks."""
    from apps.scoring import engine

    values = []
    for oid in office_ids:
        rv = results.get((oid, OWNER))
        if rv is None and allow_implementing:
            rv = results.get((oid, IMPLEMENTING))
        values.append((oid, _metric(rv, profile)))
    return [(r.office_id, r.rank, r.value) for r in engine.rank(values)]


def _metric(rv, profile):
    from apps.scoring import engine

    if rv is None:
        return None
    return engine.ranking_metric_value(rv.cum_plan, rv.cum_actual, rv.variance, profile)


class DashboardView(APIView):
    def get(self, request):
        p = request.query_params
        period = get_period(p.get("period"))
        view = IMPLEMENTING if p.get("view") == IMPLEMENTING else OWNER
        office = perm.get_office_or_404(request.user, p.get("office"))
        month = period.month_index
        results = read.get_agency_results(period)
        profile = read.period_profile(period, results)
        rv = results.get((str(office.id), view))

        scope = perm.scope(request.user)
        visible = {str(o.id): o for o in scope}
        children = [
            o
            for o in Office.objects.filter(parent=office).order_by("sort_order", "name")
            if str(o.id) in visible
        ]
        ancestors = [
            o
            for o in Office.objects.filter(pk__in=office.ancestor_ids).order_by("path")
            if str(o.id) in visible
        ]

        rankings = []
        if len(children) >= 1:
            rankings.append(
                {
                    "set": {"kind": "children", "id": str(office.id), "name": f"Offices under {office.code}"},
                    "rows": ranking_rows(
                        results,
                        visible,
                        rank_set(
                            results, [str(c.id) for c in children], profile, month, allow_implementing=False
                        ),
                    ),
                }
            )
        groups = {}
        for m in (
            OfficeGroupMember.objects.select_related("group")
            # Groups shown: those with a member at or beneath this office (all of them on the root).
            .filter(
                office_id__in=list(visible),
                group_id__in=OfficeGroupMember.objects.filter(office__path__startswith=office.path).values(
                    "group_id"
                ),
            )
            .order_by("group__sort_order", "group__name")
        ):
            groups.setdefault(m.group, []).append(str(m.office_id))
        for group, member_ids in groups.items():
            ordered = sorted(member_ids, key=lambda oid: visible[oid].path)
            rankings.append(
                {
                    "set": {"kind": "group", "id": str(group.id), "name": group.name},
                    "rows": ranking_rows(
                        results, visible, rank_set(results, ordered, profile, month, allow_implementing=True)
                    ),
                }
            )

        periods = list(period.fiscal_year.periods.order_by("month_index"))
        data = {
            "office": {
                **office_ref(office),
                "has_children": bool(children),
                "ancestors": [office_ref(a) for a in ancestors],
            },
            "period": {
                "id": str(period.id),
                "month_index": month,
                "start_date": period.start_date.isoformat(),
                "status": period.status,
                "fiscal_year": {"id": str(period.fiscal_year_id), "label": period.fiscal_year.label},
            },
            "months": [pp.start_date.isoformat() for pp in periods],
            "view": view,
            "views": [v for v in (OWNER, IMPLEMENTING) if (str(office.id), v) in results],
            "final": period.is_locked,
            "label": "FINAL" if period.is_locked else "PROVISIONAL",
            "has_result": rv is not None,
            "headline": read.headline_of(rv),
            "rank_sibling": rv.rank_sibling if rv else None,
            "plan_version": rv.plan_version if rv else None,
            "series": series(rv, month) if rv else None,
            "quarters": quarters(rv, month, profile) if rv else [],
            "indicators": rv.indicators if rv else [],
            "children": [
                {"office": office_ref(c), "result": summary(results.get((str(c.id), OWNER)))}
                for c in children
            ],
            "rankings": rankings,
        }
        return Response(data)


class DashboardActivitiesView(APIView):
    """GET ``?office&period[&view]`` — the activity list behind an office's figures (P8.3)."""

    def get(self, request):
        p = request.query_params
        period = get_period(p.get("period"))
        view = IMPLEMENTING if p.get("view") == IMPLEMENTING else OWNER
        office = perm.get_office_or_404(request.user, p.get("office"))
        rv = read.get_result(period, office, view)
        offices = {str(o.id): o.code for o in Office.objects.all()}
        rows = [
            {
                **a,
                "owner_office_code": offices.get(a.get("owner_office_id"), ""),
                "implementing_office_code": offices.get(a.get("implementing_office_id"), ""),
            }
            for a in (rv.activities if rv else [])
        ]
        return Response(
            {
                "office": office_ref(office),
                "label": "FINAL" if period.is_locked else "PROVISIONAL",
                "headline": read.headline_of(rv),
                "activities": rows,
            }
        )


class ActivityHistoryView(APIView):
    """GET ``?lineage&period`` — one activity month by month with its files (P8.3)."""

    def get(self, request):
        from apps.reporting import rules
        from apps.reporting.models import ActivityActual, Attachment

        period = get_period(request.query_params.get("period"))
        ref = (
            rules.activity_in_period(request.query_params.get("lineage"), period)
            if request.query_params.get("lineage")
            else None
        )
        if ref is None or not rules.can_view_activity(request.user, ref):
            raise Http404()
        act = ref.activity
        planned = {t.period.month_index: t.planned_qty for t in act.targets.select_related("period")}
        actuals = {
            a.period.month_index: a
            for a in ActivityActual.objects.select_related("period").filter(
                activity_lineage_id=act.lineage_id, period__fiscal_year=period.fiscal_year
            )
        }
        files = {}
        for f in Attachment.objects.filter(
            target_type="activity_actual", target_id__in=[a.pk for a in actuals.values()], deleted_at=None
        ).select_related("period", "uploaded_by"):
            files.setdefault(f.period.month_index, []).append(
                {
                    "id": str(f.id),
                    "file_name": f.file_name,
                    "download_url": f"/api/v1/attachments/{f.id}/download",
                }
            )
        months = []
        for pp in period.fiscal_year.periods.order_by("month_index"):
            m = pp.month_index
            a = actuals.get(m)
            months.append(
                {
                    "month_index": m,
                    "start_date": pp.start_date.isoformat(),
                    "period_id": str(pp.id),
                    "status": pp.status,
                    "planned": plain(planned.get(m, Decimal(0))),
                    "actual": plain(a.actual_qty) if a else None,
                    "actual_amount": jsonable(a.actual_amount) if a else None,
                    "remarks": a.remarks if a else "",
                    "delay_reason": a.delay_reason if a else "",
                    "files": files.get(m, []),
                }
            )
        return Response(
            {
                "activity": {
                    "lineage_id": str(act.lineage_id),
                    "code": act.code,
                    "title": act.title,
                    "unit": act.unit,
                    "measure_type": act.measure_type,
                    "annual_target": plain(act.annual_target),
                    "total_cost": jsonable(act.total_cost),
                    "owner_office": office_ref(ref.owner_office),
                    "implementing_office": office_ref(ref.implementing_office),
                    "editable": rules.can_edit_activity(request.user, ref),
                },
                "months": months,
            }
        )


class RankingsView(APIView):
    """GET ``?period[&set=children:<office id>|group:<group id>]`` — one ranking set with each office's
    rank change against the previous month, plus the sets the user can choose from (P8.4)."""

    def get(self, request):

        period = get_period(request.query_params.get("period"))
        scope = {str(o.id): o for o in perm.scope(request.user)}
        parents = {}
        for o in Office.objects.filter(parent_id__in=[o.pk for o in scope.values()]).order_by("path"):
            if str(o.id) in scope:
                parents.setdefault(str(o.parent_id), []).append(o)
        sets = [
            {
                "key": f"children:{pid}",
                "kind": "children",
                "name": f"Offices under {scope[pid].code} {scope[pid].name}",
            }
            for pid in sorted(parents, key=lambda p: scope[p].path)
            if len(parents[pid]) >= 2
        ]
        group_members = {}
        for m in OfficeGroupMember.objects.select_related("group").filter(office_id__in=list(scope)):
            group_members.setdefault(m.group, []).append(str(m.office_id))
        for g in sorted(group_members, key=lambda g: (g.sort_order, g.name)):
            sets.append({"key": f"group:{g.id}", "kind": "group", "name": g.name})

        key = request.query_params.get("set") or (sets[0]["key"] if sets else "")
        kind, _, ident = key.partition(":")
        if kind == "children" and ident in parents:
            member_ids, allow_impl = [str(o.id) for o in parents[ident]], False
        elif kind == "group" and any(str(g.id) == ident for g in group_members):
            group = next(g for g in group_members if str(g.id) == ident)
            member_ids, allow_impl = sorted(group_members[group], key=lambda oid: scope[oid].path), True
        elif not sets:
            return Response({"sets": [], "set": None, "rows": []})
        else:
            raise Http404()

        results = read.get_agency_results(period)
        profile = read.period_profile(period, results)
        current = rank_set(results, member_ids, profile, period.month_index, allow_implementing=allow_impl)
        previous_ranks = {}
        prev = period.fiscal_year.periods.filter(month_index=period.month_index - 1).first()
        if prev is not None:
            prev_results = read.get_agency_results(prev)
            prev_profile = read.period_profile(prev, prev_results)
            previous_ranks = {
                oid: rank
                for oid, rank, _ in rank_set(
                    prev_results, member_ids, prev_profile, prev.month_index, allow_implementing=allow_impl
                )
            }
        rows = ranking_rows(results, scope, current)
        for row in rows:
            before = previous_ranks.get(row["office"]["id"])
            row["previous_rank"] = before
            row["change"] = (before - row["rank"]) if (before and row["rank"]) else None
        return Response(
            {
                "sets": sets,
                "set": next((s for s in sets if s["key"] == key), None),
                "metric": profile.ranking_metric,
                "label": "FINAL" if period.is_locked else "PROVISIONAL",
                "previous_month": prev.start_date.isoformat() if prev else None,
                "rows": rows,
            }
        )

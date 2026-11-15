"""Whole-agency results for one month (MASTERPLAN 7.6–7.9, P7.1).

``compute_agency(period)`` loads the year's approved plans, targets and actuals once, calls the
engine for every plan, rolls results up the owner tree (7.6), computes every implementing view
(7.7) and ranks siblings and group members (7.8). ``compute_live(period, office, view)`` returns one
office's entry. Nothing here re-implements a formula: every number comes from ``apps.scoring``.
"""

import uuid
from collections import defaultdict
from dataclasses import dataclass, field

from apps.planning.models import Activity, Indicator, Plan, ReportingPeriod
from apps.results.services import (
    activity_input,
    indicator_input,
    load_activity_actuals,
    load_indicator_actuals,
    load_planned,
)
from apps.scoring import engine
from apps.scoring.types import OfficeResult
from apps.structure.models import Office, OfficeGroup

OWNER = "owner"
IMPLEMENTING = "implementing"


@dataclass
class OfficeEntry:
    office: Office
    view: str
    result: OfficeResult | None
    plan_version: int | None = None
    own_plan: OfficeResult | None = None  # the office's own plan alone (owner view only)
    rank_sibling: int | None = None
    group_ranks: dict = field(default_factory=dict)  # group id -> rank (or None)
    activity_rows: list = field(default_factory=list)  # (Activity, ActivityResult)
    indicator_rows: list = field(default_factory=list)  # (Indicator, IndicatorResult)
    actuals: dict = field(default_factory=dict)  # lineage -> {month: ActivityActual} (shared)
    indicator_actuals: dict = field(default_factory=dict)  # lineage -> {month: IndicatorActual} (shared)
    planned: dict = field(default_factory=dict)  # activity id -> {month: planned qty} (shared)


@dataclass
class AgencyResults:
    period: ReportingPeriod
    profile: object
    offices: dict  # office id -> Office
    entries: dict  # (office id, view) -> OfficeEntry
    groups: list  # [(OfficeGroup, [office ids])]
    group_rankings: dict = field(default_factory=dict)  # group id -> [RankingRow]
    sibling_rankings: dict = field(default_factory=dict)  # parent id -> [RankingRow]

    def get(self, office_id, view=OWNER) -> OfficeEntry | None:
        return self.entries.get((office_id, view))


def compute_agency(period: ReportingPeriod) -> AgencyResults:
    fy = period.fiscal_year
    profile = fy.profile.to_engine()
    month = period.month_index
    offices = {o.id: o for o in Office.objects.select_related("level").order_by("path")}

    plans = {p.office_id: p for p in Plan.objects.filter(fiscal_year=fy, status=Plan.Status.APPROVED)}
    rows = list(
        Activity.objects.filter(plan__in=plans.values(), row_kind=Activity.RowKind.ACTIVITY)
        .select_related("plan")
        .order_by("plan_id", "sort_order")
    )
    inds = list(
        Indicator.objects.filter(plan__in=plans.values())
        .prefetch_related("targets__period")
        .order_by("sort_order")
    )
    actuals = load_activity_actuals(fy)  # the whole year, as plain rows (P8.8)
    ind_actuals = load_indicator_actuals(fy)
    planned = load_planned(rows)
    inputs = {r.id: activity_input(r, actuals, planned_map=planned) for r in rows}

    rows_by_plan, inds_by_plan, rows_by_impl = defaultdict(list), defaultdict(list), defaultdict(list)
    for r in rows:
        rows_by_plan[r.plan_id].append(r)
        rows_by_impl[r.implementing_office_id or r.plan.office_id].append(r)
    for i in inds:
        inds_by_plan[i.plan_id].append(i)

    entries: dict = {}

    # Own plan of each office (7.2–7.5).
    own: dict = {}
    for office_id, plan in plans.items():
        plan_rows, plan_inds = rows_by_plan[plan.id], inds_by_plan[plan.id]
        res = engine.plan_result(
            [inputs[r.id] for r in plan_rows], [indicator_input(i, ind_actuals) for i in plan_inds], profile
        )
        own[office_id] = (plan, res, plan_rows, plan_inds)

    # Owner tree roll-up, deepest offices first (7.6).
    children = defaultdict(list)
    for o in offices.values():
        if o.parent_id:
            children[o.parent_id].append(o.id)
    rolled: dict = {}
    for office_id in sorted(offices, key=lambda oid: -offices[oid].depth):
        components = []
        if office_id in own:
            components.append(own[office_id][1])
        components += [rolled[c] for c in children[office_id] if rolled.get(c) is not None]
        if not components:
            rolled[office_id] = None
        elif len(components) == 1 and office_id in own:  # its own plan only
            rolled[office_id] = own[office_id][1]
        else:
            rolled[office_id] = engine.rollup(components, profile)
        plan_info = own.get(office_id)
        entry = OfficeEntry(
            office=offices[office_id],
            view=OWNER,
            result=rolled[office_id],
            plan_version=plan_info[0].version if plan_info else None,
            own_plan=plan_info[1] if plan_info else None,
        )
        if plan_info:
            entry.activity_rows = list(zip(plan_info[2], plan_info[1].activities, strict=True))
            entry.indicator_rows = list(zip(plan_info[3], plan_info[1].indicators, strict=True))
        entry.actuals, entry.indicator_actuals, entry.planned = actuals, ind_actuals, planned
        entries[(office_id, OWNER)] = entry

    # Implementing view (7.7): display and ranking only.
    for office_id, impl_rows in rows_by_impl.items():
        res = engine.implementing_result([inputs[r.id] for r in impl_rows], profile)
        entries[(office_id, IMPLEMENTING)] = OfficeEntry(
            office=offices[office_id],
            view=IMPLEMENTING,
            result=res,
            activity_rows=list(zip(impl_rows, res.activities, strict=True)),
            actuals=actuals,
            planned=planned,
        )

    agency = AgencyResults(
        period=period,
        profile=profile,
        offices=offices,
        entries=entries,
        groups=[
            (g, list(g.members.order_by("office__path").values_list("office_id", flat=True)))
            for g in OfficeGroup.objects.order_by("sort_order", "name")
        ],
    )

    # Ranking (7.8): siblings by the owner view; group members by the owner view, or the
    # implementing view when the member owns no plan.
    def value(office_id, allow_implementing=False):
        entry = entries.get((office_id, OWNER))
        result = entry.result if entry else None
        if result is None and allow_implementing and (office_id, IMPLEMENTING) in entries:
            result = entries[(office_id, IMPLEMENTING)].result
        return engine.ranking_value(result, month, profile)

    for parent_id, kids in children.items():
        ordered = sorted(kids, key=lambda k: offices[k].path)
        rows_ranked = engine.rank([(str(k), value(k)) for k in ordered])
        agency.sibling_rankings[parent_id] = rows_ranked
        for r in rows_ranked:
            entries[(offices_key(r.office_id), OWNER)].rank_sibling = r.rank
    for group, members in agency.groups:
        rows_ranked = engine.rank([(str(m), value(m, allow_implementing=True)) for m in members])
        agency.group_rankings[group.id] = rows_ranked
        for r in rows_ranked:
            key = (offices_key(r.office_id), OWNER)
            if key in entries:
                entries[key].group_ranks[str(group.id)] = r.rank
    return agency


def offices_key(office_id: str) -> uuid.UUID:
    return uuid.UUID(office_id)


def compute_live(period: ReportingPeriod, office: Office, view: str = OWNER) -> OfficeEntry | None:
    return compute_agency(period).get(office.id, view)

"""Plan lifecycle and bulk editing (MASTERPLAN P5.3, P5.7, P5.9)."""

import uuid
from decimal import Decimal, InvalidOperation

from django.db import transaction
from django.utils import timezone

from apps.audit import services as audit
from apps.planning.models import (
    Activity,
    ActivityTarget,
    FiscalYear,
    Indicator,
    IndicatorTarget,
    Plan,
)
from apps.planning.numbers import plain
from apps.planning.services import PlanningError
from apps.planning.validation import validate_plan
from apps.structure.models import Office

ROW_FIELDS = ("row_kind", "code", "title", "sort_order", "measure_type", "unit")
DECIMAL_FIELDS = ("annual_target", "unit_cost", "total_cost", "manual_weight")
INDICATOR_FIELDS = ("code", "name", "kind", "unit", "aggregation", "sort_order")


def _dec(value, field, allow_none=True):
    if value is None or value == "":
        if allow_none:
            return None
        return Decimal(0)
    try:
        d = Decimal(str(value).replace(",", ""))
    except InvalidOperation as exc:
        raise PlanningError("bad_number", f"{field}: '{value}' is not a number.") from exc
    if not d.is_finite():
        raise PlanningError("bad_number", f"{field}: '{value}' is not a number.")
    return d


def create_draft(office: Office, fy: FiscalYear) -> Plan:
    if Plan.objects.filter(office=office, fiscal_year=fy).exists():
        raise PlanningError("plan_exists", "This office already has a plan for that fiscal year.")
    if fy.status == FiscalYear.Status.CLOSED:
        raise PlanningError("year_closed", "That fiscal year is closed.")
    return Plan.objects.create(office=office, fiscal_year=fy)


def require_draft(plan: Plan) -> None:
    if plan.status != Plan.Status.DRAFT:
        raise PlanningError("not_draft", f"This plan is {plan.status}; only a draft can be edited.")


@transaction.atomic
def bulk_save(plan: Plan, data: dict) -> dict[str, str]:
    """Apply a grid save in one transaction. Returns client_key -> new id for created rows.

    ``data``: ``rows`` (upserted: ``id`` for existing, ``client_key`` for new; ``parent`` is an id
    or a client key; ``targets`` 12 values; ``amounts`` 12 values or null), ``indicators`` (same
    shape), ``deleted_rows``, ``deleted_indicators``, optional ``notes``.
    """
    require_draft(plan)
    periods = {p.month_index: p for p in plan.fiscal_year.periods.all()}
    keymap: dict[str, str] = {}

    for row_id in data.get("deleted_rows", []):
        Activity.objects.filter(plan=plan, pk=row_id).delete()
    for ind_id in data.get("deleted_indicators", []):
        Indicator.objects.filter(plan=plan, pk=ind_id).delete()

    rows_in = list(data.get("rows", []))
    existing = {str(a.id): a for a in plan.rows.all()}
    # First pass: create/update rows without parents (parents may be new rows).
    saved: list[tuple[Activity, dict]] = []
    for item in rows_in:
        if item.get("id"):
            row = existing.get(str(item["id"]))
            if row is None:
                raise PlanningError("unknown_row", "A row being saved does not belong to this plan.")
        else:
            row = Activity(plan=plan, lineage_id=uuid.uuid4())
        for f in ROW_FIELDS:
            if f in item:
                setattr(
                    row,
                    f,
                    item[f] if item[f] is not None else ("" if f in ("code", "unit", "title") else None),
                )
        if row.row_kind not in Activity.RowKind.values:
            raise PlanningError("bad_row_kind", f"Unknown row kind {row.row_kind!r}.")
        for f in DECIMAL_FIELDS:
            if f in item:
                setattr(row, f, _dec(item[f], f))
        if "implementing_office_id" in item:
            office_id = item["implementing_office_id"]
            if office_id:
                office = Office.objects.filter(pk=office_id).first()  # RLS: same agency only
                if office is None:
                    raise PlanningError("bad_office", "Unknown implementing office.")
                row.implementing_office = office
            else:
                row.implementing_office = None
        if row.row_kind != Activity.RowKind.ACTIVITY:
            row.measure_type = None
            row.annual_target = row.unit_cost = row.total_cost = row.manual_weight = None
            row.implementing_office = None
        elif row.implementing_office_id is None:
            row.implementing_office_id = plan.office_id
        row.title = row.title or ""
        row.save()
        if item.get("client_key"):
            keymap[str(item["client_key"])] = str(row.id)
        saved.append((row, item))

    # Second pass: parents and monthly targets.
    for row, item in saved:
        if "parent" in item:
            parent_ref = item["parent"]
            parent_id = keymap.get(str(parent_ref), parent_ref) if parent_ref else None
            if parent_id and not Activity.objects.filter(plan=plan, pk=parent_id).exists():
                raise PlanningError("bad_parent", "A row's parent is not in this plan.")
            if str(parent_id or "") != str(row.parent_id or ""):
                row.parent_id = parent_id
                row.save(update_fields=["parent"])
        if "targets" in item and row.row_kind == Activity.RowKind.ACTIVITY:
            amounts = item.get("amounts") or [None] * 12
            _save_targets(row, periods, item["targets"], amounts)

    _save_indicators(plan, periods, data.get("indicators", []), keymap)
    if "notes" in data:
        plan.notes = str(data["notes"])
    plan.save()
    return keymap


def _save_targets(row: Activity, periods: dict, values: list, amounts: list) -> None:
    if len(values) != 12:
        raise PlanningError("bad_targets", "Monthly targets need 12 values.")
    current = {t.period.month_index: t for t in row.targets.select_related("period")}
    for month in range(1, 13):
        qty = _dec(values[month - 1], "monthly target", allow_none=False)
        amount = _dec(amounts[month - 1], "monthly amount") if amounts else None
        target = current.get(month)
        if target is None:
            if qty == 0 and amount is None:
                continue
            ActivityTarget.objects.create(
                activity=row, period=periods[month], planned_qty=qty, planned_amount=amount
            )
        elif target.planned_qty != qty or target.planned_amount != amount:
            target.planned_qty, target.planned_amount = qty, amount
            target.save()


def _save_indicators(plan: Plan, periods: dict, items: list, keymap: dict) -> None:
    existing = {str(i.id): i for i in plan.indicators.all()}
    for item in items:
        if item.get("id"):
            ind = existing.get(str(item["id"]))
            if ind is None:
                raise PlanningError(
                    "unknown_indicator", "An indicator being saved does not belong to this plan."
                )
        else:
            ind = Indicator(plan=plan, lineage_id=uuid.uuid4())
        for f in INDICATOR_FIELDS:
            if f in item and item[f] is not None:
                setattr(ind, f, item[f])
        if "annual_target" in item:
            ind.annual_target = _dec(item["annual_target"], "annual_target", allow_none=False)
        if "weight" in item:
            ind.weight = _dec(item["weight"], "weight")
        ind.save()
        if item.get("client_key"):
            keymap[str(item["client_key"])] = str(ind.id)
        if "targets" in item:
            values = item["targets"]
            if len(values) != 12:
                raise PlanningError("bad_targets", "Monthly targets need 12 values.")
            current = {t.period.month_index: t for t in ind.targets.select_related("period")}
            for month in range(1, 13):
                value = _dec(values[month - 1], "indicator target", allow_none=False)
                target = current.get(month)
                if target is None:
                    if value:
                        IndicatorTarget.objects.create(
                            indicator=ind, period=periods[month], planned_value=value
                        )
                elif target.planned_value != value:
                    target.planned_value = value
                    target.save()


def set_approved_budget(plan: Plan, value) -> Plan:
    budget = _dec(value, "approved_budget")
    plan.approved_budget = budget.quantize(Decimal("0.01")) if budget is not None else None
    plan.save(update_fields=["approved_budget", "updated_at"])
    return plan


@transaction.atomic
def submit(plan: Plan, user) -> list[dict]:
    require_draft(plan)
    issues = validate_plan(plan, for_submit=True)
    errors = [i for i in issues if i["severity"] == "error"]
    if errors:
        raise PlanningError("invalid_plan", f"Fix {len(errors)} problem(s) before submitting.", issues=issues)
    plan.status = Plan.Status.SUBMITTED
    plan.submitted_by = user
    plan.submitted_at = timezone.now()
    with audit.suppressed():
        plan.save()
    audit.record("submit", plan, after={"version": plan.version}, office_id=plan.office_id)
    from apps.alerts import services as alerts

    alerts.plan_submitted(plan)
    return issues


@transaction.atomic
def approve(plan: Plan, user) -> Plan:
    if plan.status != Plan.Status.SUBMITTED:
        raise PlanningError("not_submitted", "Only a submitted plan can be approved.")
    issues = validate_plan(plan, for_submit=True)
    if any(i["severity"] == "error" for i in issues):
        raise PlanningError("invalid_plan", "The plan has problems that must be fixed first.", issues=issues)
    previous = Plan.objects.select_for_update().filter(
        office=plan.office, fiscal_year=plan.fiscal_year, status=Plan.Status.APPROVED
    )
    superseded = [str(p.id) for p in previous]
    with audit.suppressed():
        previous.update(status=Plan.Status.SUPERSEDED)
        plan.status = Plan.Status.APPROVED
        plan.approved_by = user
        plan.approved_at = timezone.now()
        plan.save()
    audit.record(
        "approve", plan, after={"version": plan.version, "superseded": superseded}, office_id=plan.office_id
    )
    return plan


@transaction.atomic
def return_to_draft(plan: Plan, user, note: str = "") -> Plan:
    if plan.status != Plan.Status.SUBMITTED:
        raise PlanningError("not_submitted", "Only a submitted plan can be returned.")
    plan.status = Plan.Status.DRAFT
    with audit.suppressed():
        plan.save()
    audit.record("return", plan, after={"version": plan.version, "note": note}, office_id=plan.office_id)
    return plan


@transaction.atomic
def clone(source: Plan, *, fiscal_year: FiscalYear | None = None, keep_lineage: bool = True) -> Plan:
    """Copy a plan's rows, targets and indicators into a new draft (P5.7 revise, P5.9 copy).

    Same fiscal year: next version, same lineage ids. Another fiscal year: version 1, new lineage
    ids, targets mapped month by month (month_index), actuals never copied.
    """
    fy = fiscal_year or source.fiscal_year
    same_year = fy.pk == source.fiscal_year_id
    version = (
        Plan.objects.filter(office=source.office, fiscal_year=fy)
        .order_by("-version")
        .values_list("version", flat=True)
        .first()
        or 0
    ) + 1
    new = Plan.objects.create(
        office=source.office,
        fiscal_year=fy,
        version=version,
        approved_budget=source.approved_budget if same_year else None,
        notes=source.notes if same_year else "",
    )
    periods = {p.month_index: p for p in fy.periods.all()}
    mapping: dict = {}
    for row in source.rows.order_by("sort_order").prefetch_related("targets__period"):
        copy = Activity.objects.create(
            plan=new,
            lineage_id=row.lineage_id if (keep_lineage and same_year) else uuid.uuid4(),
            row_kind=row.row_kind,
            code=row.code,
            title=row.title,
            sort_order=row.sort_order,
            measure_type=row.measure_type,
            unit=row.unit,
            annual_target=row.annual_target,
            unit_cost=row.unit_cost,
            total_cost=row.total_cost,
            manual_weight=row.manual_weight,
            implementing_office_id=row.implementing_office_id,
        )
        mapping[row.id] = copy
        ActivityTarget.objects.bulk_create(
            [
                ActivityTarget(
                    activity=copy,
                    period=periods[t.period.month_index],
                    planned_qty=t.planned_qty,
                    planned_amount=t.planned_amount,
                )
                for t in row.targets.all()
            ]
        )
    for row in source.rows.exclude(parent=None):
        mapping[row.id].parent = mapping[row.parent_id]
        mapping[row.id].save(update_fields=["parent"])
    for ind in source.indicators.prefetch_related("targets__period"):
        copy = Indicator.objects.create(
            plan=new,
            lineage_id=ind.lineage_id if (keep_lineage and same_year) else uuid.uuid4(),
            code=ind.code,
            name=ind.name,
            kind=ind.kind,
            unit=ind.unit,
            annual_target=ind.annual_target,
            weight=ind.weight,
            aggregation=ind.aggregation,
            sort_order=ind.sort_order,
        )
        IndicatorTarget.objects.bulk_create(
            [
                IndicatorTarget(
                    indicator=copy, period=periods[t.period.month_index], planned_value=t.planned_value
                )
                for t in ind.targets.all()
            ]
        )
    return new


def revise(plan: Plan) -> Plan:
    """'Revise plan' on an approved plan: a new draft version with the same lineage ids (P5.7)."""
    if plan.status != Plan.Status.APPROVED:
        raise PlanningError("not_approved", "Only the approved plan can be revised.")
    if Plan.objects.filter(
        office=plan.office,
        fiscal_year=plan.fiscal_year,
        status__in=[Plan.Status.DRAFT, Plan.Status.SUBMITTED],
    ).exists():
        raise PlanningError("revision_open", "A revision of this plan is already in progress.")
    new = clone(plan)
    audit.record(
        "revise", new, after={"from_version": plan.version, "version": new.version}, office_id=plan.office_id
    )
    return new


def compare(old: Plan, new: Plan) -> dict:
    """Rows added, removed and changed between two versions, matched by lineage id (P5.7)."""

    def rows(plan):
        out = {}
        for r in plan.rows.prefetch_related("targets__period"):
            targets = {t.period.month_index: plain(t.planned_qty) for t in r.targets.all() if t.planned_qty}
            out[r.lineage_id] = {
                "code": r.code,
                "title": r.title,
                "row_kind": r.row_kind,
                "annual_target": plain(r.annual_target) if r.annual_target is not None else None,
                "total_cost": str(r.total_cost) if r.total_cost is not None else None,
                "unit": r.unit,
                "implementing_office_id": str(r.implementing_office_id) if r.implementing_office_id else None,
                "targets": targets,
            }
        return out

    a, b = rows(old), rows(new)
    added = [{"lineage_id": str(k), **b[k]} for k in b.keys() - a.keys()]
    removed = [{"lineage_id": str(k), **a[k]} for k in a.keys() - b.keys()]
    changed = []
    for k in a.keys() & b.keys():
        diff = {f: {"before": a[k][f], "after": b[k][f]} for f in a[k] if a[k][f] != b[k][f]}
        if diff:
            changed.append(
                {"lineage_id": str(k), "code": b[k]["code"], "title": b[k]["title"], "changes": diff}
            )
    key = lambda r: (r.get("code") or "", r.get("title") or "")  # noqa: E731
    return {
        "from_version": old.version,
        "to_version": new.version,
        "added": sorted(added, key=key),
        "removed": sorted(removed, key=key),
        "changed": sorted(changed, key=key),
    }

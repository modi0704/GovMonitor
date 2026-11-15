"""Plan validation (MASTERPLAN P5.4). Run on save (as warnings) and on submit (as errors).

Each issue: ``{"row": id|None, "indicator": id|None, "field", "code", "message", "severity"}``.
Rules marked ``always_warning`` never block submission (the cost may be typed by hand).
"""

from collections import Counter
from decimal import Decimal

from apps.planning.models import Activity, Plan
from apps.planning.numbers import plain
from apps.scoring import engine
from apps.scoring.types import ActivityInput

SUM_TOLERANCE = Decimal("0.0001")
ALWAYS_WARNING = {"cost_mismatch", "zero_cost", "indicator_targets_sum"}


def _issue(code, message, *, row=None, indicator=None, field=""):
    return {
        "row": str(row) if row else None,
        "indicator": str(indicator) if indicator else None,
        "field": field,
        "code": code,
        "message": message,
    }


def validate_plan(plan: Plan, *, for_submit: bool) -> list[dict]:
    profile = plan.fiscal_year.profile
    rows = list(plan.rows.select_related("implementing_office").prefetch_related("targets__period"))
    activities = [r for r in rows if r.row_kind == Activity.RowKind.ACTIVITY]
    issues: list[dict] = []

    codes = Counter(r.code.strip().upper() for r in rows if r.code.strip())
    for r in rows:
        if r.code.strip() and codes[r.code.strip().upper()] > 1:
            issues.append(
                _issue("duplicate_code", f"Code {r.code} is used more than once.", row=r.id, field="code")
            )
        if not r.title.strip():
            issues.append(_issue("title_required", "Every row needs a title.", row=r.id, field="title"))

    for a in activities:
        label = a.code or a.title[:40]
        target = a.annual_target or Decimal(0)
        if not a.measure_type:
            issues.append(
                _issue(
                    "measure_required", f"{label}: choose how it is measured.", row=a.id, field="measure_type"
                )
            )
        if target <= 0:
            issues.append(
                _issue(
                    "no_target", f"{label}: the annual target is missing.", row=a.id, field="annual_target"
                )
            )
        monthly = [t.planned_qty for t in a.targets.all()]
        if a.measure_type in ("quantity", "money") and target > 0:
            total = sum(monthly, Decimal(0))
            if abs(total - target) > SUM_TOLERANCE:
                issues.append(
                    _issue(
                        "targets_sum",
                        f"{label}: monthly targets add up to {plain(total)}, not the annual target "
                        f"{plain(target)}.",
                        row=a.id,
                        field="targets",
                    )
                )
        if a.measure_type == "recurring" and not any(v > 0 for v in monthly):
            issues.append(
                _issue("no_target", f"{label}: no month has a planned level.", row=a.id, field="targets")
            )
        if a.unit_cost is not None and a.annual_target is not None and a.total_cost is not None:
            expected = (a.annual_target * a.unit_cost).quantize(Decimal("0.01"))
            if expected != a.total_cost:
                issues.append(
                    _issue(
                        "cost_mismatch",
                        f"{label}: total cost {a.total_cost:,.2f} differs from "
                        f"target × unit cost ({expected:,.2f}).",
                        row=a.id,
                        field="total_cost",
                    )
                )
        if profile.weighting == "cost_share" and not (a.total_cost or 0):
            issues.append(
                _issue(
                    "zero_cost",
                    f"{label}: no cost, so it carries no weight under cost-share weighting.",
                    row=a.id,
                    field="total_cost",
                )
            )
        if a.implementing_office_id and not a.implementing_office:
            issues.append(
                _issue(
                    "bad_office",
                    f"{label}: unknown implementing office.",
                    row=a.id,
                    field="implementing_office",
                )
            )
        elif a.implementing_office and not a.implementing_office.is_active:
            issues.append(
                _issue(
                    "inactive_office",
                    f"{label}: the implementing office is inactive.",
                    row=a.id,
                    field="implementing_office",
                )
            )

    if profile.weighting == "manual" and activities:
        inputs = [
            ActivityInput(
                id=str(a.id),
                measure_type="quantity",
                annual_target=Decimal(1),
                total_cost=Decimal(0),
                planned=(Decimal(0),) * 12,
                manual_weight=a.manual_weight,
            )
            for a in activities
        ]
        if not engine.manual_weights_valid(inputs):
            total = sum((a.manual_weight or Decimal(0) for a in activities), Decimal(0))
            issues.append(
                _issue(
                    "weights_sum", f"Weights add up to {total * 100:.4f}%, not 100%.", field="manual_weight"
                )
            )

    if not activities:
        issues.append(_issue("empty_plan", "The plan has no activities yet."))

    for ind in plan.indicators.prefetch_related("targets"):
        if not ind.name.strip():
            issues.append(
                _issue("title_required", "Every indicator needs a name.", indicator=ind.id, field="name")
            )
        if ind.annual_target <= 0:
            issues.append(
                _issue(
                    "no_target",
                    f"{ind.name[:40]}: the annual target is missing.",
                    indicator=ind.id,
                    field="annual_target",
                )
            )
        monthly = sum((t.planned_value for t in ind.targets.all()), Decimal(0))
        if (
            ind.aggregation == "sum"
            and ind.annual_target > 0
            and monthly
            and abs(monthly - ind.annual_target) > SUM_TOLERANCE
        ):
            issues.append(
                _issue(
                    "indicator_targets_sum",
                    f"{ind.name[:40]}: monthly targets add up to {plain(monthly)}, not "
                    f"{plain(ind.annual_target)}.",
                    indicator=ind.id,
                    field="targets",
                )
            )

    for issue in issues:
        issue["severity"] = "error" if for_submit and issue["code"] not in ALWAYS_WARNING else "warning"
    return issues

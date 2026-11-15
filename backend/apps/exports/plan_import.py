"""Plan import from the office sheet layout (MASTERPLAN 9.4, D17, P9.7).

Rows are read from row 8. An outline row has its text in the column of its kind (B..G); an
activity is a PLAN row (column N) with its text in H, paired with the ACTUAL row beneath it, whose
values are ignored. Below the TOTAL COST row, an OUTPUT INDICATORS header starts the indicators
(two rows each). The rows are saved as a **draft** plan through the same services as the plan
editor and checked with the same validation (P5.4). Nothing is kept if any row has an error: the
caller runs this inside a transaction and the error list names each row.
"""

import re
from dataclasses import dataclass, field
from decimal import Decimal, InvalidOperation

import openpyxl

from apps.exports.layout import DEFAULT, OfficeSheetLayout
from apps.planning import plans as plan_svc
from apps.planning.models import Activity, FiscalYear
from apps.planning.services import PlanningError
from apps.planning.validation import validate_plan

KIND_RANK = {
    "outcome": 0,
    "outcome_indicator": 1,
    "output": 2,
    "output_indicator": 3,
    "program": 4,
    "project": 5,
    "activity": 6,
}
# A leading token is a code when it carries a digit or a dot (e.g. "RDID1.1.", "PME-3", "X1.").
CODE = re.compile(r"^[^\s]*[\d.][^\s]*$")
MAX_ROWS = 20000


class ImportFailed(Exception):
    def __init__(self, issues: list[dict]):
        super().__init__(f"{len(issues)} problem(s) in the file")
        self.issues = issues


@dataclass
class Parsed:
    rows: list = field(default_factory=list)  # bulk_save row payloads
    indicators: list = field(default_factory=list)
    issues: list = field(default_factory=list)
    sheet_row: dict = field(default_factory=dict)  # client_key -> sheet row number
    sheet: str = ""


def issue(row: int | None, message: str, column: str = "") -> dict:
    return {"row": row, "column": column, "message": message}


def split_code(text: str) -> tuple[str, str]:
    text = " ".join(str(text).split())
    head, _, rest = text.partition(" ")
    if rest and CODE.match(head):
        return head[:40], rest
    return "", text


def _text(ws, ref: str) -> str:
    value = ws[ref].value
    if value is None:
        return ""
    return str(value).strip()


def _number(ws, ref: str, problems: list, row: int, *, required=False, allow_negative=False):
    value = ws[ref].value
    if value is None or (isinstance(value, str) and not value.strip()):
        if required:
            problems.append(issue(row, f"{ref}: a number is needed here.", ref.rstrip("0123456789")))
        return None
    if isinstance(value, bool):
        problems.append(issue(row, f"{ref}: '{value}' is not a number.", ref.rstrip("0123456789")))
        return None
    try:
        number = Decimal(str(value).replace(",", "").strip())
    except InvalidOperation:
        problems.append(issue(row, f"{ref}: '{value}' is not a number.", ref.rstrip("0123456789")))
        return None
    if not number.is_finite():
        problems.append(issue(row, f"{ref}: '{value}' is not a number.", ref.rstrip("0123456789")))
        return None
    if number < 0 and not allow_negative:
        problems.append(issue(row, f"{ref}: cannot be negative.", ref.rstrip("0123456789")))
        return None
    return number


def pick_sheet(wb, office_code: str):
    names = [n for n in wb.sheetnames if n.upper() not in ("SUMMARY", "INSTRUCTIONS")]
    for n in names:
        if n.upper() == (office_code or "").upper():
            return wb[n]
    for n in names:
        if n.upper() == "PLAN":
            return wb[n]
    return wb[names[0]] if names else None


def parse(file, office_code: str, profile, L: OfficeSheetLayout = DEFAULT) -> Parsed:
    """Read the sheet into plan-editor payloads. ``profile``: the year's ScoringProfile (manual
    weights are read from column M only under manual weighting)."""
    out = Parsed()
    try:
        wb = openpyxl.load_workbook(file, data_only=True)  # cached values of any formulas
    except Exception:  # noqa: BLE001 — any unreadable file is one problem for the user
        out.issues.append(issue(None, "The file could not be read as an Excel workbook (.xlsx)."))
        return out
    ws = pick_sheet(wb, office_code)
    if ws is None:
        out.issues.append(issue(None, "The workbook has no plan sheet."))
        return out
    out.sheet = ws.title
    if ws.max_row > MAX_ROWS:
        out.issues.append(issue(None, f"The sheet has more than {MAX_ROWS} rows."))
        return out

    outline_cols = {col: kind for kind, col in L.outline_cols.items() if kind != "activity"}
    activity_col = L.outline_cols["activity"]
    text_cols = [*outline_cols, activity_col]
    months = L.month_cols
    stack: list = []  # (rank, client_key)
    r = L.first_data_row
    last = ws.max_row
    sort = 0
    while r <= last:
        marker = _text(ws, f"{L.remarks_col}{r}").upper()
        texts = {c: _text(ws, f"{c}{r}") for c in text_cols}
        if any(t.upper() == L.total_label for t in texts.values()) or texts[activity_col].upper() == (
            L.indicator_header
        ):
            break
        filled = [c for c in text_cols if texts[c]]
        if marker == L.actual_marker:
            out.issues.append(issue(r, "This ACTUAL row has no PLAN row above it.", L.remarks_col))
            r += 1
            continue
        if marker == L.plan_marker:
            problems: list = []
            if not texts[activity_col]:
                problems.append(
                    issue(r, f"The activity's text belongs in column {activity_col}.", activity_col)
                )
            stray = [c for c in filled if c != activity_col]
            if stray:
                problems.append(issue(r, f"A PLAN row has text only in column {activity_col}.", stray[0]))
            target = _number(ws, f"{L.target_col}{r}", problems, r, required=True)
            unit_cost = _number(ws, f"{L.unit_cost_col}{r}", problems, r)
            total_cost = _number(ws, f"{L.total_cost_col}{r}", problems, r)
            weight = None
            if profile.weighting == "manual":
                weight = _number(ws, f"{L.weight_col}{r}", problems, r, required=True)
            planned = [_number(ws, f"{c}{r}", problems, r) for c in months]
            key = f"r{r}"
            while stack and stack[-1][0] >= KIND_RANK["activity"]:
                stack.pop()
            code, title = split_code(texts[activity_col])
            comment = ws[f"{L.weighted_cols[0]}{r}"].comment
            recurring = bool(comment and comment.text.strip().startswith(L.recurring_comment.split(":")[0]))
            row = {
                "client_key": key,
                "parent": stack[-1][1] if stack else None,
                "row_kind": "activity",
                "code": code,
                "title": title,
                "sort_order": sort,
                "measure_type": "recurring" if recurring else "quantity",
                "unit": _text(ws, f"{L.unit_col}{r}")[:60],
                "annual_target": _plain(target),
                "unit_cost": _plain(unit_cost),
                "total_cost": _plain(total_cost if total_cost is not None else Decimal(0)),
                "targets": [_plain(v if v is not None else Decimal(0)) for v in planned],
            }
            if weight is not None:
                row["manual_weight"] = _plain(weight)
            out.issues.extend(problems)
            out.rows.append(row)
            out.sheet_row[key] = r
            sort += 10
            # The ACTUAL row beneath belongs to this activity; its values are not imported.
            r += 2 if _text(ws, f"{L.remarks_col}{r + 1}").upper() == L.actual_marker else 1
            continue
        if not filled:
            r += 1
            continue
        if texts[activity_col]:
            out.issues.append(
                issue(r, f"Mark activity rows with {L.plan_marker} in column {L.remarks_col}.", L.remarks_col)
            )
            r += 1
            continue
        if len(filled) > 1:
            out.issues.append(issue(r, "Put each outline row's text in one column only.", filled[1]))
            r += 1
            continue
        col = filled[0]
        kind = outline_cols[col]
        rank = KIND_RANK[kind]
        while stack and stack[-1][0] >= rank:
            stack.pop()
        key = f"r{r}"
        code, title = split_code(texts[col])
        out.rows.append(
            {
                "client_key": key,
                "parent": stack[-1][1] if stack else None,
                "row_kind": kind,
                "code": code,
                "title": title,
                "sort_order": sort,
            }
        )
        out.sheet_row[key] = r
        stack.append((rank, key))
        sort += 10
        r += 1

    _parse_indicators(ws, r, out, profile, L)
    return out


def _parse_indicators(ws, start: int, out: Parsed, profile, L: OfficeSheetLayout) -> None:
    header = next(
        (
            r
            for r in range(start, ws.max_row + 1)
            if _text(ws, f"{L.indicator_code_col}{r}").upper() == L.indicator_header
        ),
        None,
    )
    if header is None:
        return
    q = header + 1
    sort = 0
    while q <= ws.max_row:
        name = _text(ws, f"{L.indicator_name_col}{q}")
        code = _text(ws, f"{L.indicator_code_col}{q}")
        if not name and not code:
            q += 1
            if q > ws.max_row or not any(
                _text(ws, f"{c}{q}") for c in (L.indicator_code_col, L.indicator_name_col)
            ):
                break
            continue
        problems: list = []
        targets = [_number(ws, f"{c}{q}", problems, q) for c in L.month_cols]
        weight = None
        if profile.indicator_weighting == "manual":
            weight = _number(ws, f"{L.indicator_weight_col}{q}", problems, q, required=True)
        if not name:
            problems.append(issue(q, f"The indicator's name belongs in column {L.indicator_name_col}.", "I"))
        values = [v if v is not None else Decimal(0) for v in targets]
        key = f"i{q}"
        item = {
            "client_key": key,
            "code": code[:40],
            "name": name,
            "kind": "output",
            "aggregation": "sum",
            "sort_order": sort,
            "annual_target": _plain(sum(values, Decimal(0))),
            "targets": [_plain(v) for v in values],
        }
        if weight is not None:
            item["weight"] = _plain(weight)
        out.issues.extend(problems)
        out.indicators.append(item)
        out.sheet_row[key] = q
        sort += 10
        q += 2  # the actual row beneath is not imported


def _plain(value):
    if value is None:
        return None
    from apps.planning.numbers import plain

    return plain(value)


def import_plan(office, fiscal_year: FiscalYear, file) -> dict:
    """Create a draft plan from the file. Raises ImportFailed with row-by-row issues; the caller's
    transaction then rolls back anything created."""
    parsed = parse(file, office.code, fiscal_year.profile)
    if parsed.issues:
        raise ImportFailed(parsed.issues)
    if not any(r["row_kind"] == "activity" for r in parsed.rows):
        raise ImportFailed([issue(None, "No activity rows were found (rows marked PLAN in column N).")])
    try:
        plan = plan_svc.create_draft(office, fiscal_year)
        keymap = plan_svc.bulk_save(plan, {"rows": parsed.rows, "indicators": parsed.indicators})
    except PlanningError as err:
        raise ImportFailed([issue(None, err.message)]) from err
    by_id = {v: parsed.sheet_row[k] for k, v in keymap.items() if k in parsed.sheet_row}
    found = validate_plan(plan, for_submit=True)
    errors = [i for i in found if i["severity"] == "error"]
    warnings = [i for i in found if i["severity"] != "error"]

    def located(i):
        ref = i.get("row") or i.get("indicator")
        return issue(by_id.get(ref), i["message"], _column_for(i.get("field", "")))

    if errors:
        raise ImportFailed([located(i) for i in errors])
    activities = plan.rows.filter(row_kind=Activity.RowKind.ACTIVITY).count()
    return {
        "plan_id": str(plan.id),
        "rows": len(parsed.rows),
        "activities": activities,
        "indicators": len(parsed.indicators),
        "sheet": parsed.sheet,
        "warnings": [located(i) for i in warnings],
    }


FIELD_COLUMNS = {"code": "H", "title": "H", "annual_target": "I", "unit_cost": "K", "total_cost": "L",
                 "manual_weight": "M", "targets": "O", "name": "I", "weight": "N"}  # fmt: skip


def _column_for(field_name: str) -> str:
    return FIELD_COLUMNS.get(field_name, "")

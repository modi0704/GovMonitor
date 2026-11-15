"""Excel export (MASTERPLAN 9, P9.2–P9.3).

One workbook per request: ``SUMMARY`` first, then one sheet per office in scope that has an approved
plan, laid out exactly as 9.1. Percentages are live formulas, each written with its computed value
as the cached result, so the file shows the right numbers before it is recalculated and keeps
giving them after. Every number the formulas cannot reproduce (recurring measures, activities
without a target, non-default scoring profiles) is written as the engine's value with a comment.
"""

import io
import re
from dataclasses import dataclass, field
from decimal import Decimal

import xlsxwriter

from apps.exports import office_sheet
from apps.exports.layout import DEFAULT, MONTH_ABBR, MONTH_FULL, OfficeSheetLayout
from apps.results.read import period_profile
from apps.results.services import load_activity_actuals, load_indicator_actuals
from apps.tenancy.models import Agency

HEADER_FILL = "#FFD965"
SUMMARY_SHEET = "SUMMARY"
INVALID_SHEET_CHARS = re.compile(r"[\[\]:*?/\\]")


def f(value) -> float:
    return float(value) if value is not None else 0.0


@dataclass
class SheetMap:
    """Where things landed on one office sheet (used by tests and the importer's round trip)."""

    name: str
    first: int  # first outline/activity row
    last: int  # last outline/activity row
    total: int  # total row t
    activity_rows: list = field(default_factory=list)  # PLAN row of each activity
    indicator_rows: list = field(default_factory=list)  # target row of each indicator
    last_row: int = 0


class Formats:
    def __init__(self, wb):
        border = {"border": 1, "border_color": "#808080"}
        self.title = wb.add_format({"bold": True, "font_size": 13})
        self.bold = wb.add_format({"bold": True})
        self.header = wb.add_format(
            {"bold": True, "bg_color": HEADER_FILL, "align": "center", "valign": "vcenter", "text_wrap": True}
            | border
        )
        self.text = wb.add_format({"text_wrap": True, "valign": "top"})
        self.outline = wb.add_format({"text_wrap": True, "valign": "top", "bold": True})
        self.qty = wb.add_format({"num_format": "#,##0.##"})
        self.money = wb.add_format({"num_format": "#,##0.00"})
        self.money_bold = wb.add_format({"num_format": "#,##0.00", "bold": True})
        self.pct = wb.add_format({"num_format": "0.00%"})
        self.pct_bold = wb.add_format({"num_format": "0.00%", "bold": True})
        self.marker = wb.add_format({"align": "center", "font_color": "#404040"})
        self.label = wb.add_format({"bold": True})
        self.indent = [wb.add_format({"indent": i}) for i in range(8)]


def sheet_name(code: str, used: set) -> str:
    base = INVALID_SHEET_CHARS.sub("-", code or "OFFICE").strip("'")[:31] or "OFFICE"
    name, n = base, 2
    while name.upper() in used:
        suffix = f"-{n}"
        name = base[: 31 - len(suffix)] + suffix
        n += 1
    used.add(name.upper())
    return name


def write_office_sheet(
    wb, ws, sheet: office_sheet.OfficeSheet, ctx: dict, fmt: Formats, L: OfficeSheetLayout = DEFAULT
) -> SheetMap:
    """Write one office sheet (9.1). ``ctx``: agency name, fiscal year label, as-of text, level-0 name."""
    months, weighted = L.month_cols, L.weighted_cols
    m_sel = sheet.month
    result = sheet.result
    exact = sheet.formulas_reproduce_engine

    # ---- Title block and header rows 5–7 ----
    ws.write(L.fiscal_year_cell, f"Fiscal Year {ctx['fiscal_year']}", fmt.title)
    ws.write(L.agency_cell, ctx["agency"], fmt.bold)
    ws.write(L.office_cell, sheet.office.name, fmt.bold)
    ws.write(L.as_of_cell, f"As of {ctx['as_of']}", fmt.bold)
    r5, r6, r7 = L.header_rows
    ws.merge_range(f"A{r5}:A{r7}", ctx["level0"].upper(), fmt.header)
    for col, text in L.outline_headers.items():
        ws.merge_range(f"{col}{r5}:{col}{r7}", text, fmt.header)
    ws.merge_range(f"{L.target_col}{r5}:{L.unit_col}{r6}", L.targets_header, fmt.header)
    ws.merge_range(f"{L.unit_cost_col}{r5}:{L.total_cost_col}{r6}", L.cost_header, fmt.header)
    for col in (L.weight_col, L.remarks_col):
        ws.merge_range(f"{col}{r5}:{col}{r6}", "", fmt.header)
    for cols in (months, weighted):
        ws.merge_range(f"{cols[0]}{r5}:{cols[-1]}{r5}", L.schedule_header, fmt.header)
        for q in range(4):
            ws.merge_range(f"{cols[q * 3]}{r6}:{cols[q * 3 + 2]}{r6}", f"Q{q + 1}", fmt.header)
    for col, text in (
        (L.target_col, L.qty_header),
        (L.unit_col, L.unit_header),
        (L.unit_cost_col, L.unit_cost_header),
        (L.total_cost_col, L.total_cost_header),
        (L.weight_col, L.weight_header),
        (L.remarks_col, L.remarks_header),
    ):
        ws.write(f"{col}{r7}", text, fmt.header)
    abbr = [MONTH_ABBR[d.month - 1] for d in sheet.month_starts]
    for i in range(12):
        ws.write(f"{months[i]}{r7}", abbr[i], fmt.header)
        ws.write(f"{weighted[i]}{r7}", abbr[i], fmt.header)

    # ---- Plan rows ----
    first = L.first_data_row
    n_rows = sum(2 if isinstance(x, office_sheet.ActivityLine) else 1 for x in sheet.rows)
    t = first + n_rows  # total row
    last = t - 1
    ws.write(f"{L.office_caps_col}{first}", sheet.office.name.upper(), fmt.bold)
    total_cost = sum(
        (x.input.total_cost for x in sheet.rows if isinstance(x, office_sheet.ActivityLine)), Decimal(0)
    )
    cost_share_formula = exact and total_cost != 0
    smap = SheetMap(name=ws.get_name(), first=first, last=last, total=t)

    r = first
    for item in sheet.rows:
        if not isinstance(item, office_sheet.ActivityLine):
            col = L.outline_cols.get(item.row_kind, L.outline_cols["activity"])
            ws.write(f"{col}{r}", f"{item.code} {item.title}".strip(), fmt.outline)
            r += 1
            continue
        row, a_res = item.row, sheet.activity_results[str(item.row.lineage_id)]
        smap.activity_rows.append(r)
        ws.write(f"{L.outline_cols['activity']}{r}", f"{row.code} {row.title}".strip(), fmt.text)
        ws.write_number(f"{L.target_col}{r}", f(row.annual_target), fmt.qty)
        ws.write(f"{L.unit_col}{r}", row.unit or "")
        if row.unit_cost is not None:
            ws.write_number(f"{L.unit_cost_col}{r}", f(row.unit_cost), fmt.money)
        ws.write_number(f"{L.total_cost_col}{r}", f(row.total_cost), fmt.money)
        if cost_share_formula:
            ws.write_formula(
                f"{L.weight_col}{r}",
                f"={L.total_cost_col}{r}/${L.total_cost_col}${t}",
                fmt.pct,
                f(a_res.weight),
            )
        else:
            ws.write_number(f"{L.weight_col}{r}", f(a_res.weight), fmt.pct)
        ws.write(f"{L.remarks_col}{r}", L.plan_marker, fmt.marker)
        ws.write(f"{L.remarks_col}{r + 1}", L.actual_marker, fmt.marker)
        for i in range(12):
            if item.planned[i]:
                ws.write_number(f"{months[i]}{r}", f(item.planned[i]), fmt.qty)
            if item.actual[i] is not None:
                ws.write_number(f"{months[i]}{r + 1}", f(item.actual[i]), fmt.qty)

        computed = item.input.measure_type == "recurring" or a_res.no_target
        comment = L.recurring_comment if item.input.measure_type == "recurring" else L.no_target_comment
        prev_p = prev_a = Decimal(0)
        for i in range(12):
            plan_w = a_res.weight * (a_res.planned_ratio[i] - prev_p)
            act_w = a_res.weight * (a_res.actual_ratio[i] - prev_a)
            prev_p, prev_a = a_res.planned_ratio[i], a_res.actual_ratio[i]
            if computed:
                ws.write_number(f"{weighted[i]}{r}", f(plan_w), fmt.pct)
                ws.write_number(f"{weighted[i]}{r + 1}", f(act_w), fmt.pct)
                continue
            target = f"${L.target_col}{r}"
            w_cell = f"${L.weight_col}{r}"
            ws.write_formula(f"{weighted[i]}{r}", f"={months[i]}{r}*{w_cell}/{target}", fmt.pct, f(plan_w))
            # The cached value follows the formula (uncapped) — the capped figure is in the totals.
            raw_act = (
                a_res.weight * f_dec(item.actual[i]) / item.input.annual_target
                if item.input.annual_target
                else Decimal(0)
            )
            ws.write_formula(
                f"{weighted[i]}{r + 1}", f"={months[i]}{r + 1}*{w_cell}/{target}", fmt.pct, f(raw_act)
            )
        if computed:
            ws.write_comment(f"{weighted[0]}{r}", comment)
            ws.write_comment(f"{weighted[0]}{r + 1}", comment)
        r += 2

    # ---- Total block ----
    for col in L.total_label_cols:
        ws.write(f"{col}{t}", L.total_label, fmt.label)
    ws.write_formula(
        f"{L.total_cost_col}{t}",
        f"=SUM({L.total_cost_col}{first}:{L.total_cost_col}{last})",
        fmt.money_bold,
        f(total_cost),
    )
    ws.write_formula(
        f"{L.weight_col}{t}",
        f"=SUM({L.weight_col}{first}:{L.weight_col}{last})",
        fmt.pct_bold,
        f(sum((a.weight for a in result.activities), Decimal(0))),
    )
    labels = [
        (t + 1, L.plan_label, L.periodic_label),
        (t + 2, None, L.cum_plan_label),
        (t + 3, L.actual_label, L.periodic_label),
        (t + 4, None, L.cum_actual_label),
        (t + 5, L.variance_label, L.periodic_label),
        (t + 6, None, L.cum_variance_label),
    ]
    for row_no, label, sub in labels:
        if label:
            ws.write(f"{L.label_col}{row_no}", label, fmt.label)
        ws.write(f"{L.sublabel_col}{row_no}", sub, fmt.label)
    rng_n = f"${L.remarks_col}${first}:${L.remarks_col}${last}"
    periodic_variance = [a - p for a, p in zip(result.periodic_actual, result.periodic_plan, strict=True)]
    series = {
        t + 1: result.periodic_plan,
        t + 2: result.cum_plan,
        t + 3: result.periodic_actual,
        t + 4: result.cum_actual,
        t + 5: periodic_variance,
        t + 6: result.variance,
    }
    for i, col in enumerate(weighted):
        prev = weighted[i - 1] if i else None
        formulas = {
            t + 1: f'=SUMIF({rng_n},"{L.plan_marker}",{col}${first}:{col}${last})',
            t + 2: f"={col}{t + 1}" + (f"+{prev}{t + 2}" if prev else ""),
            t + 3: f'=SUMIF({rng_n},"{L.actual_marker}",{col}${first}:{col}${last})',
            t + 4: f"={col}{t + 3}" + (f"+{prev}{t + 4}" if prev else ""),
            t + 5: f"={col}{t + 3}-{col}{t + 1}",
            t + 6: f"={col}{t + 4}-{col}{t + 2}",
        }
        for row_no, formula in formulas.items():
            value = f(series[row_no][i])
            if exact:
                ws.write_formula(f"{col}{row_no}", formula, fmt.pct, value)
            else:
                ws.write_number(f"{col}{row_no}", value, fmt.pct)
    if not exact:
        ws.write_comment(f"{weighted[0]}{t + 1}", L.profile_comment)

    m_i = m_sel - 1
    cum_actual_cell = f"{weighted[m_i]}{t + 4}"
    used = result.funds_used_est[m_i]
    ws.write(f"{L.label_col}{t + 8}", L.funds_total_label, fmt.label)
    ws.write_formula(
        f"{L.value_col}{t + 8}", f"={L.total_cost_col}{t}", fmt.money_bold, f(result.funds_total)
    )
    ws.write(f"{L.label_col}{t + 9}", L.funds_used_label, fmt.label)
    ws.write_formula(
        f"{L.value_col}{t + 9}", f"={cum_actual_cell}*{L.value_col}{t + 8}", fmt.money_bold, f(used)
    )
    ws.write(f"{L.label_col}{t + 10}", L.funds_remaining_label, fmt.label)
    ws.write_formula(
        f"{L.value_col}{t + 10}",
        f"={L.value_col}{t + 8}-{L.value_col}{t + 9}",
        fmt.money_bold,
        f(result.funds_total - used),
    )
    ws.write(f"{L.label_col}{t + 11}", L.status_label, fmt.label)
    ws.write(f"{L.value_col}{t + 11}", sheet.status, fmt.bold)

    # ---- Indicators ----
    h = t + L.indicator_header_offset
    ws.write(f"{L.indicator_code_col}{h}", L.indicator_header, fmt.header)
    ws.write(f"{L.indicator_total_col}{h}", L.indicator_total_header, fmt.header)
    ws.write(f"{L.indicator_weight_col}{h}", L.indicator_weight_header, fmt.header)
    full = [MONTH_FULL[d.month - 1] for d in sheet.month_starts]
    for i in range(12):
        ws.write(f"{months[i]}{h}", full[i], fmt.header)
        ws.write(f"{weighted[i]}{h}", full[i], fmt.header)
    q = h + 1
    for line in sheet.indicators:
        ind = line.indicator
        smap.indicator_rows.append(q)
        total = sum(line.targets, Decimal(0))
        done = sum((v for v in line.actual if v is not None), Decimal(0))
        ws.write(f"{L.indicator_code_col}{q}", ind.code or "")
        ws.write(f"{L.indicator_name_col}{q}", ind.name, fmt.text)
        tc = L.indicator_total_col
        ws.write_formula(f"{tc}{q}", f"=SUM({months[0]}{q}:{months[-1]}{q})", fmt.qty, f(total))
        ws.write_formula(f"{tc}{q + 1}", f"=SUM({months[0]}{q + 1}:{months[-1]}{q + 1})", fmt.qty, f(done))
        ws.write_number(f"{L.indicator_weight_col}{q}", f(line.weight), fmt.pct)
        for i in range(12):
            if line.targets[i]:
                ws.write_number(f"{months[i]}{q}", f(line.targets[i]), fmt.qty)
            if line.actual[i] is not None:
                ws.write_number(f"{months[i]}{q + 1}", f(line.actual[i]), fmt.qty)
            for row_no, value in ((q, line.targets[i]), (q + 1, line.actual[i])):
                if total == 0:
                    ws.write_number(f"{weighted[i]}{row_no}", 0, fmt.pct)
                    continue
                cached = f_dec(value) / total * line.weight
                formula = f"=({months[i]}{row_no}/${tc}{q})*${L.indicator_weight_col}{q}"
                ws.write_formula(f"{weighted[i]}{row_no}", formula, fmt.pct, f(cached))
        q += 2
    smap.last_row = max(q - 1, h)

    # ---- Sheet setup ----
    ws.freeze_panes(first - 1, 14)  # O8
    widths = {"A": 14, "B": 30, "C": 30, "D": 30, "E": 30, "F": 30, "G": 30, "H": 50, "I": 10, "J": 10}
    widths |= {"K": 14, "L": 16, "M": 9, "N": 10}
    for col, width in widths.items():
        ws.set_column(f"{col}:{col}", width)
    ws.set_column(f"{months[0]}:{months[-1]}", 8)
    ws.set_column(f"{L.empty_cols[0]}:{L.empty_cols[-1]}", 3)
    ws.set_column(f"{weighted[0]}:{weighted[-1]}", 9)
    ws.set_landscape()
    ws.set_paper(8)  # A3
    ws.fit_to_pages(1, 0)
    ws.repeat_rows(r5 - 1, r7 - 1)
    ws.print_area(f"A1:{L.last_col}{smap.last_row}")
    return smap


def f_dec(value) -> Decimal:
    return Decimal(0) if value is None else Decimal(value)


def context_for(sc) -> dict:
    agency = Agency.objects.get(pk=sc.period.agency_id)
    level0 = _level0_name()
    return {
        "agency": agency.name,
        "fiscal_year": sc.fiscal_year.label,
        "as_of": sc.period.start_date.strftime("%B %Y"),
        "level0": level0,
    }


def _level0_name() -> str:
    from apps.structure.models import OrgLevel

    level = OrgLevel.objects.order_by("depth").first()
    return level.name if level else "Agency"


def build(sc, layout: OfficeSheetLayout = DEFAULT) -> tuple[bytes, dict]:
    """The workbook for one export scope. Returns (file bytes, summary for the job result)."""
    out = io.BytesIO()
    wb = xlsxwriter.Workbook(out, {"in_memory": True})
    fmt = Formats(wb)
    ctx = context_for(sc)
    summary_ws = wb.add_worksheet(SUMMARY_SHEET)
    used = {SUMMARY_SHEET}
    fy = sc.fiscal_year
    actuals = load_activity_actuals(fy)
    ind_actuals = load_indicator_actuals(fy)
    profile = period_profile(sc.period)
    sheets = {}
    for office in sc.offices:
        data = office_sheet.load(office, sc.period, actuals, ind_actuals, profile)
        if data is None:
            continue
        ws = wb.add_worksheet(sheet_name(office.code, used))
        sheets[office.id] = write_office_sheet(wb, ws, data, ctx, fmt, layout)
    rows = write_summary(summary_ws, sc, ctx, fmt, profile, sheets)
    wb.close()
    return out.getvalue(), {"offices": rows, "sheets": len(sheets) + 1}


SUMMARY_HEADERS = (
    ("Office", 16),
    ("Name", 44),
    ("Funds total", 18),
    ("Cumulative plan", 14),
    ("Cumulative actual", 14),
    ("Variance", 12),
    ("Status", 14),
    ("Indicator score", 14),
    ("Rank among siblings", 12),
)
SUMMARY_HEADER_ROW = 9  # 1-based


def profile_text(profile) -> str:
    from apps.scoring.presets import PRESET_DESCRIPTIONS

    name = profile.preset or "custom"
    described = PRESET_DESCRIPTIONS.get(name)
    if described:
        return f"{name.replace('_', ' ')} — {described}"
    tolerance = f"{float(profile.on_time_tolerance) * 100:g}"
    ceiling = "yes" if profile.cap_at_100 else "no"
    parts = [
        f"weights: {profile.weighting.replace('_', ' ')}",
        f"100% ceiling: {ceiling}",
        f"on-time tolerance: {tolerance} points",
        f"roll-up: {profile.rollup.replace('_', ' ')}",
    ]
    return "custom — " + "; ".join(parts)


def write_summary(ws, sc, ctx, fmt, profile, sheets: dict) -> int:
    """SUMMARY sheet (9.2): one row per office in scope, in tree order, indented by depth. Every
    figure comes from the results read path, so it is the dashboard's number for the same month."""
    from apps.planning.models import ReportingPeriod
    from apps.results import read

    results = read.get_agency_results(sc.period)
    final = sc.period.status == ReportingPeriod.Status.LOCKED
    ws.write("A1", "Performance summary", fmt.title)
    ws.write("A2", ctx["agency"], fmt.bold)
    ws.write("A3", f"Fiscal Year {ctx['fiscal_year']}")
    ws.write("A4", f"As of {ctx['as_of']}")
    ws.write("A5", f"Scoring preset: {profile_text(profile)}")
    ws.write(
        "A6",
        "FINAL — this month is locked" if final else "PROVISIONAL — this month is still open and may change",
        fmt.bold,
    )
    ws.write("A7", f"{'Implementing' if sc.view == 'implementing' else 'Owner'} view")
    if not office_sheet.formulas_reproduce(profile):
        ws.write(
            "A8",
            "Under this scoring profile the total rows of each office sheet hold values computed by "
            "the system instead of formulas.",
        )
    hr = SUMMARY_HEADER_ROW - 1
    for c, (text, width) in enumerate(SUMMARY_HEADERS):
        ws.write(hr, c, text, fmt.header)
        ws.set_column(c, c, width)
    row = hr + 1
    for office in sc.offices:
        rv = results.get((str(office.id), sc.view))
        indent = fmt.indent[min(sc.depth(office), len(fmt.indent) - 1)]
        smap = sheets.get(office.id) if sc.view == "owner" else None
        if smap is not None:
            ws.write_url(row, 0, f"internal:'{smap.name}'!A1", indent, string=office.code)
        else:
            ws.write(row, 0, office.code, indent)
        ws.write(row, 1, office.name)
        if rv is None:
            ws.write(row, 6, "No result")
        else:
            ws.write_number(row, 2, f(rv.funds_total), fmt.money)
            ws.write_number(row, 3, f(rv.cum_plan), fmt.pct)
            ws.write_number(row, 4, f(rv.cum_actual), fmt.pct)
            ws.write_number(row, 5, f(rv.variance), fmt.pct)
            ws.write(row, 6, rv.status_label)
            if rv.indicator_score is not None:
                ws.write_number(row, 7, f(rv.indicator_score), fmt.pct)
            if rv.rank_sibling is not None:
                ws.write_number(row, 8, rv.rank_sibling)
        row += 1
    ws.freeze_panes(SUMMARY_HEADER_ROW, 2)
    ws.set_landscape()
    ws.set_paper(9)  # A4
    ws.fit_to_pages(1, 0)
    ws.print_area(0, 0, max(row - 1, hr), len(SUMMARY_HEADERS) - 1)
    return row - hr - 1

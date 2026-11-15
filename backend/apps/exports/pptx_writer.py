"""PowerPoint export (MASTERPLAN 10, D11, P10.1).

A 16:9 deck for one month and one scope: title, the scope's overall slide, one dashboard slide per
office in tree order (with a bar chart of its offices when it has any), ranking slides, indicator
tables and a notes slide. Charts are native and editable. Every number comes from the results read
path that the dashboard uses (``apps.results.read``); ranking order is the engine's (7.8).
"""

import io
import logging
from dataclasses import dataclass, field
from decimal import Decimal

from django.utils import timezone
from pptx import Presentation
from pptx.chart.data import CategoryChartData
from pptx.dml.color import RGBColor
from pptx.enum.chart import XL_CHART_TYPE, XL_LEGEND_POSITION
from pptx.enum.shapes import MSO_SHAPE
from pptx.enum.text import MSO_ANCHOR, PP_ALIGN
from pptx.util import Inches, Pt

from apps.exports.layout import MONTH_ABBR
from apps.exports.pptx_layout import (
    DEFAULT,
    DEFAULT_SETTINGS,
    FONT,
    MAX_TABLE_ROWS,
    SLIDE_GROUPS,
    SLIDE_H,
    SLIDE_W,
)
from apps.exports.text_fit import fit
from apps.planning.models import ReportingPeriod
from apps.results import read
from apps.results.agency import IMPLEMENTING, OWNER
from apps.results.dashboard_api import rank_set
from apps.structure.models import Office, OfficeGroupMember
from apps.structure.ordering import tree_key
from apps.tenancy.models import Agency

BLANK_LAYOUT = 6
log = logging.getLogger(__name__)


def rgb(hex_color: str) -> RGBColor:
    return RGBColor.from_string(hex_color.lstrip("#").upper())


def d(value) -> Decimal | None:
    return None if value is None else Decimal(str(value))


def pct(value, digits=2) -> str:
    return "—" if value is None else f"{Decimal(str(value)) * 100:,.{digits}f}%"


def money(value, symbol: str) -> str:
    return "—" if value is None else f"{symbol}{Decimal(str(value)):,.2f}"


@dataclass
class DeckData:
    """Everything the deck shows, read once."""

    agency: Agency
    period: ReportingPeriod
    view: str
    final: bool
    profile: object
    results: dict
    offices: list  # offices in scope with a result, tree order
    root: Office
    month_labels: list
    children: dict = field(default_factory=dict)  # office id -> [child offices with a result]
    without_result: list = field(default_factory=list)
    scope_offices: list = field(default_factory=list)  # every office in scope, tree order

    def rv(self, office) -> read.ResultView | None:
        return self.results.get((str(office.id), self.view))


@dataclass
class DeckMap:
    """What was put on which slide (used by tests)."""

    slides: list = field(default_factory=list)  # (kind, key)


class Deck:
    def __init__(self, data: DeckData, settings: dict, layout=DEFAULT, logo: bytes | None = None):
        self.data = data
        self.s = {**DEFAULT_SETTINGS, **(settings or {})}
        self.L = layout
        self.logo = logo
        self.prs = Presentation()
        self.prs.slide_width, self.prs.slide_height = SLIDE_W, SLIDE_H
        self.map = DeckMap()

    # ---- primitives ----
    def new_slide(self, kind: str, key: str = ""):
        slide = self.prs.slides.add_slide(self.prs.slide_layouts[BLANK_LAYOUT])
        self.map.slides.append((kind, key))
        return slide

    def text(self, slide, box, text, size, *, bold=False, color="1B2430", align=PP_ALIGN.LEFT, fill=None,
             anchor=MSO_ANCHOR.MIDDLE, fit_width=True, name=None):  # fmt: skip
        x, y, w, h = box.emu() if hasattr(box, "emu") else box
        shape = slide.shapes.add_textbox(x, y, w, h) if fill is None else slide.shapes.add_shape(
            MSO_SHAPE.RECTANGLE, x, y, w, h
        )  # fmt: skip
        if fill is not None:
            shape.fill.solid()
            shape.fill.fore_color.rgb = rgb(fill)
            shape.line.fill.background()
            shape.shadow.inherit = False
        if name:
            shape.name = name
        tf = shape.text_frame
        tf.word_wrap = True  # single lines are already cut to fit; wrapping keeps alignment exact
        tf.vertical_anchor = anchor
        tf.margin_left = tf.margin_right = Inches(0.08)
        width_pt = w / 12700 - 12
        lines = text if isinstance(text, list) else [text]
        for i, line in enumerate(lines):
            line_text, line_size = line if isinstance(line, tuple) else (line, size)
            p = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
            p.alignment = align
            run = p.add_run()
            run.text = fit(line_text, width_pt, line_size.pt, bold) if fit_width else line_text
            run.font.size = line_size
            run.font.bold = bold
            run.font.name = FONT
            run.font.color.rgb = rgb(color)
        return shape

    def header(self, slide, title: str):
        L = self.L
        bar = L.header
        chip_w = L.header_chip_w
        title_box = (Inches(bar.x), Inches(bar.y), Inches(bar.w - 2 * chip_w - 0.1), Inches(bar.h))
        self.text(slide, title_box, title.upper(), L.header_title_size, bold=True, color="FFFFFF",
                  fill=self.s["primary_color"], name="header-title")  # fmt: skip
        month = self.data.period.start_date.strftime("%B %Y").upper()
        x = bar.x + bar.w - 2 * chip_w
        self.text(slide, (Inches(x), Inches(bar.y), Inches(chip_w), Inches(bar.h)), month, Pt(16), bold=True,
                  color="FFFFFF", fill=self.s["primary_color"], align=PP_ALIGN.CENTER,
                  name="header-month")  # fmt: skip
        label = "FINAL" if self.data.final else "PROVISIONAL"
        self.text(slide, (Inches(x + chip_w), Inches(bar.y), Inches(chip_w), Inches(bar.h)), label, Pt(16),
                  bold=True, color="1B2430", fill=self.s["accent_color"], align=PP_ALIGN.CENTER,
                  name="header-label")  # fmt: skip

    # ---- slides ----
    def title_slide(self):
        slide = self.new_slide("title")
        L, data = self.L, self.data
        if self.logo:
            x, y, w, h = L.logo.emu()
            try:
                slide.shapes.add_picture(io.BytesIO(self.logo), x, y, height=h)
            except Exception:  # noqa: BLE001 — a broken logo must not stop the export
                log.warning("export logo could not be placed", exc_info=True)
        width = Inches(SLIDE_W.inches - 2 * L.margin)
        rows = [
            (data.agency.name, Pt(28), True, "1B2430"),
            (self.s["report_title"], Pt(36), True, self.s["primary_color"]),
            (f"As of {data.period.start_date.strftime('%B %Y')}", Pt(22), False, "1B2430"),
            ("FINAL" if data.final else "PROVISIONAL — the month is still open", Pt(16), True, "5B6878"),
        ]
        for top, (text, size, bold, color) in zip(L.title_lines, rows, strict=True):
            self.text(slide, (Inches(L.margin), Inches(top), width, Inches(0.8)), text, size, bold=bold,
                      color=color, align=PP_ALIGN.CENTER)  # fmt: skip

    def office_slide(self, office, kind: str):
        data, L = self.data, self.L
        rv = data.rv(office)
        slide = self.new_slide(kind, str(office.id))
        self.header(
            slide, f"{office.name} ({'accomplishment report' if kind == 'office' else 'overall performance'})"
        )
        # Tiles: plan, actual, variance, status
        tiles = [
            ("PLAN", pct(rv.cum_plan), *L.tile_colors["plan"]),
            ("ACTUAL", pct(rv.cum_actual), *L.tile_colors["actual"]),
            ("VARIANCE", pct(rv.variance), *L.tile_colors["variance"]),
            ("STATUS", rv.status_label, *L.status_colors.get(rv.status_kind, L.status_colors["on_time"])),
        ]
        h = L.tiles.h / 4
        for i, (label, value, bg, fg) in enumerate(tiles):
            top = L.tiles.y + i * h
            self.text(slide, (Inches(L.tiles.x), Inches(top), Inches(L.tiles.w), Inches(h - 0.06)),
                      [(label, L.tile_label_size), value], L.tile_value_size, bold=True, color=fg, fill=bg,
                      align=PP_ALIGN.CENTER, name=f"tile-{label.lower()}")  # fmt: skip
        # Where the office sits (path), under the tiles
        ancestors = [a for a in office.ancestor_ids if a != str(office.id)]
        by_id = {str(o.id): o for o in data.offices} | {str(data.root.id): data.root}
        path = " › ".join(by_id[a].code for a in ancestors if a in by_id)
        lines = [f"{office.code} · {office.name}"] + ([path] if path else [])
        self.text(slide, L.office_path, lines, Pt(11), color="5B6878", anchor=MSO_ANCHOR.TOP, fit_width=False)

        kids = data.children.get(office.id, [])
        line_box = L.line_chart_with_children if kids else L.line_chart
        self.line_chart(slide, line_box, rv)
        if kids:
            self.children_chart(slide, L.children_chart, kids)
        self.funds(slide, rv)
        score = rv.indicator_score
        score_text = pct(score) if score is not None else "No indicators"
        self.text(slide, L.indicator_tile, [("INDICATOR SCORE", Pt(11)), score_text],
                  Pt(20), bold=True, color=self.s["primary_color"], fill="F4F6F9", align=PP_ALIGN.CENTER,
                  name="tile-indicators")  # fmt: skip

    def line_chart(self, slide, box, rv):
        month = self.data.period.month_index
        plan = [float(d(v)) for v in rv.series.get("cum_plan", [])]
        actual = [float(d(v)) if i < month else None for i, v in enumerate(rv.series.get("cum_actual", []))]
        cd = CategoryChartData(number_format="0%")
        cd.categories = self.data.month_labels
        cd.add_series("Cumulative plan", plan)
        cd.add_series("Cumulative actual", actual)
        frame = slide.shapes.add_chart(XL_CHART_TYPE.LINE_MARKERS, *box.emu(), cd)
        frame.name = "chart-scurve"
        chart = frame.chart
        chart.font.size = Pt(10)
        chart.font.name = FONT
        chart.has_title = True
        chart.chart_title.text_frame.text = "S-curve: cumulative plan and actual"
        chart.chart_title.text_frame.paragraphs[0].runs[0].font.size = Pt(14)
        chart.has_legend = True
        chart.legend.position = XL_LEGEND_POSITION.BOTTOM
        chart.legend.include_in_layout = False
        chart.value_axis.tick_labels.number_format = "0%"
        chart.value_axis.tick_labels.number_format_is_linked = False
        chart.value_axis.has_major_gridlines = True
        for series, color in zip(
            chart.plots[0].series, (self.s["primary_color"], self.s["actual_color"]), strict=True
        ):
            series.format.line.color.rgb = rgb(color)
            series.format.line.width = Pt(2.5)
            series.marker.format.fill.solid()
            series.marker.format.fill.fore_color.rgb = rgb(color)
            series.smooth = False

    def children_chart(self, slide, box, kids):
        cd = CategoryChartData(number_format="0.00%")
        cd.categories = [fit(k.code, 80, 9) for k in kids]
        cd.add_series("Cumulative plan", [float(self.data.rv(k).cum_plan) for k in kids])
        cd.add_series("Cumulative actual", [float(self.data.rv(k).cum_actual) for k in kids])
        frame = slide.shapes.add_chart(XL_CHART_TYPE.COLUMN_CLUSTERED, *box.emu(), cd)
        frame.name = "chart-children"
        chart = frame.chart
        chart.font.size = Pt(10)
        chart.font.name = FONT
        chart.has_title = True
        chart.chart_title.text_frame.text = "Offices beneath: cumulative plan and actual"
        chart.chart_title.text_frame.paragraphs[0].runs[0].font.size = Pt(12)
        chart.has_legend = True
        chart.legend.position = XL_LEGEND_POSITION.BOTTOM
        chart.legend.include_in_layout = False
        chart.value_axis.tick_labels.number_format = "0%"
        chart.value_axis.tick_labels.number_format_is_linked = False
        for series, color in zip(
            chart.plots[0].series, (self.s["primary_color"], self.s["actual_color"]), strict=True
        ):
            series.format.fill.solid()
            series.format.fill.fore_color.rgb = rgb(color)

    def funds(self, slide, rv):
        L, sym = self.L, self.s["currency_symbol"]
        h = read.headline_of(rv)
        used = d(h["funds_used_actual"]) if h["funds_used_actual"] is not None else d(h["funds_used_est"])
        remaining = d(h["funds_remaining"])
        cd = CategoryChartData(number_format=f'"{sym}"#,##0.00')
        cd.categories = ["Funds used", "Funds remaining"]
        cd.add_series("Funds", [float(used), float(max(remaining, Decimal(0)))])
        frame = slide.shapes.add_chart(XL_CHART_TYPE.DOUGHNUT, *L.doughnut.emu(), cd)
        frame.name = "chart-funds"
        chart = frame.chart
        chart.font.size = Pt(10)
        chart.font.name = FONT
        chart.has_title = True
        chart.chart_title.text_frame.text = "Funds"
        chart.chart_title.text_frame.paragraphs[0].runs[0].font.size = Pt(12)
        chart.has_legend = True
        chart.legend.position = XL_LEGEND_POSITION.BOTTOM
        chart.legend.include_in_layout = False
        plot = chart.plots[0]
        for point, color in zip(plot.series[0].points, (self.s["actual_color"], "D6DDE6"), strict=True):
            point.format.fill.solid()
            point.format.fill.fore_color.rgb = rgb(color)
        plot.has_data_labels = True
        plot.data_labels.number_format = "0%"
        plot.data_labels.number_format_is_linked = False
        plot.data_labels.show_percentage = True
        plot.data_labels.show_value = False
        plot.data_labels.font.size = Pt(10)
        lines = [
            f"Total {money(h['funds_total'], sym)}",
            f"Used {money(used, sym)}" + ("" if h["funds_used_actual"] is not None else " (estimate)"),
            f"Remaining {money(remaining, sym)}",
        ]
        self.text(slide, L.funds_text, lines, Pt(12), anchor=MSO_ANCHOR.TOP, name="funds-text")

    def table_slides(self, kind, key, title, headers, rows, widths, aligns):
        """Tables of at most MAX_TABLE_ROWS rows; longer ones continue on the next slide."""
        L = self.L
        chunks = [rows[i : i + MAX_TABLE_ROWS] for i in range(0, len(rows), MAX_TABLE_ROWS)] or [[]]
        for n, chunk in enumerate(chunks):
            slide = self.new_slide(kind, key)
            self.header(slide, title + (" (continued)" if n else ""))
            x, y, w, _ = L.table.emu()
            row_h = Inches(0.4)
            shape = slide.shapes.add_table(len(chunk) + 1, len(headers), x, y, w, row_h * (len(chunk) + 1))
            shape.name = f"table-{kind}"
            table = shape.table
            total = sum(widths)
            for c, frac in enumerate(widths):
                table.columns[c].width = int(w * frac / total)
            for r, values in enumerate([headers, *chunk]):
                for c, value in enumerate(values):
                    cell = table.cell(r, c)
                    width_pt = table.columns[c].width / 12700 - 14
                    size = L.table_header_font if r == 0 else L.table_font
                    cell.text = fit(str(value), width_pt, size.pt, bold=(r == 0))
                    para = cell.text_frame.paragraphs[0]
                    para.alignment = aligns[c]
                    for run in para.runs:
                        run.font.size = size
                        run.font.name = FONT
                        run.font.bold = r == 0
                        if r == 0:
                            run.font.color.rgb = rgb("FFFFFF")
                    if r == 0:
                        cell.fill.solid()
                        cell.fill.fore_color.rgb = rgb(self.s["primary_color"])

    def ranking_slides(self):
        data = self.data
        month = data.period.month_index
        for key, name, members, allow_impl in ranking_sets(data):
            ranked = rank_set(data.results, [str(m.id) for m in members], data.profile, month,
                              allow_implementing=allow_impl)  # fmt: skip
            by_id = {str(o.id): o for o in members}
            rows = []
            for office_id, rank, _value in ranked:
                o = by_id[office_id]
                rv = data.results.get((office_id, OWNER)) or (
                    data.results.get((office_id, IMPLEMENTING)) if allow_impl else None
                )
                rows.append(
                    [rank or "—", f"{o.code} {o.name}", pct(rv.cum_actual) if rv else "No result",
                     pct(rv.variance) if rv else "—", rv.status_label if rv else "—"]
                )  # fmt: skip
            self.table_slides("ranking", key, f"Ranking · {name}",
                              ["Rank", "Office", "Cumulative actual", "Variance", "Status"], rows,
                              [0.8, 6.5, 2, 1.6, 1.6],
                              [PP_ALIGN.CENTER, PP_ALIGN.LEFT, PP_ALIGN.RIGHT, PP_ALIGN.RIGHT,
                               PP_ALIGN.CENTER])  # fmt: skip

    def indicator_slides(self):
        data = self.data
        for office in data.offices:
            full = read.get_result(data.period, office, data.view)
            inds = full.indicators if full else []
            if not inds:
                continue
            rows = [
                [f"{i.get('code') or ''} {i['name']}".strip(), _num(i["annual_target"]),
                 _num(i["actual_to_date"]),
                 pct(i["rate"])]
                for i in inds
            ]  # fmt: skip
            self.table_slides("indicators", str(office.id), f"{office.name} · indicators",
                              ["Indicator", "Annual target", "Actual to date", "Rate"], rows, [7, 2, 2, 1.5],
                              [PP_ALIGN.LEFT, PP_ALIGN.RIGHT, PP_ALIGN.RIGHT, PP_ALIGN.RIGHT])  # fmt: skip

    def notes_slide(self, user, profile_text: str):
        slide = self.new_slide("notes")
        self.header(slide, "Notes")
        data = self.data
        tz = data.agency.timezone
        try:
            import zoneinfo

            now = timezone.now().astimezone(zoneinfo.ZoneInfo(tz))
        except Exception:  # noqa: BLE001
            now = timezone.now()
        lines = [
            f"Scoring preset: {profile_text}",
            f"Month: {data.period.start_date.strftime('%B %Y')} — "
            + ("FINAL (locked)" if data.final else "PROVISIONAL (still open; figures may change)"),
            "View: "
            + (
                "activities each office carries out"
                if data.view == IMPLEMENTING
                else "each office’s own plan"
            ),
            f"Generated: {now:%d %B %Y %H:%M} ({tz})",
            f"Generated by: {getattr(user, 'email', None) or 'the system'}",
        ]
        if data.without_result:
            names = ", ".join(o.code for o in data.without_result[:20])
            more = f" and {len(data.without_result) - 20} more" if len(data.without_result) > 20 else ""
            lines.append(f"Offices with no result this month (not shown): {names}{more}")
        L = self.L
        self.text(slide, (Inches(L.margin), Inches(1.3), Inches(SLIDE_W.inches - 2 * L.margin), Inches(5.4)),
                  lines, Pt(16), anchor=MSO_ANCHOR.TOP, fit_width=False, name="notes-text")  # fmt: skip

    def footers(self):
        L = self.L
        n = len(self.prs.slides)
        for i, slide in enumerate(self.prs.slides, start=1):
            if i == 1:
                continue
            x, y, w, h = L.footer.emu()
            half = int(w / 2)
            if self.s.get("footer_text"):
                self.text(slide, (x, y, half, h), self.s["footer_text"], L.footer_size, color="5B6878",
                          name="footer-text")  # fmt: skip
            self.text(slide, (x + half, y, w - half, h), f"Page {i} of {n}", L.footer_size, color="5B6878",
                      align=PP_ALIGN.RIGHT, name="footer-page")  # fmt: skip

    def save(self) -> bytes:
        out = io.BytesIO()
        self.prs.save(out)
        return out.getvalue()


def _num(value) -> str:
    if value is None or value == "":
        return "—"
    v = Decimal(str(value))
    return f"{v:,.0f}" if v == v.to_integral() else f"{v:,.4f}".rstrip("0").rstrip(".")


def ranking_sets(data: DeckData) -> list:
    """(key, name, member offices, allow implementing) — children of each parent in scope with at
    least two children, in tree order, then each office group with members in scope (10)."""
    in_scope = {o.id: o for o in data.scope_offices}
    by_id = {str(k): v for k, v in in_scope.items()}
    parents: dict = {}
    for o in sorted(in_scope.values(), key=lambda o: tree_key(o, by_id)):
        if o.parent_id in in_scope:
            parents.setdefault(o.parent_id, []).append(o)
    sets = [
        (f"children:{pid}", f"Offices under {in_scope[pid].code} {in_scope[pid].name}", kids, False)
        for pid, kids in sorted(parents.items(), key=lambda kv: tree_key(in_scope[kv[0]], by_id))
        if len(kids) >= 2
    ]
    groups: dict = {}
    for m in OfficeGroupMember.objects.select_related("group").filter(office_id__in=list(in_scope)):
        groups.setdefault(m.group, []).append(in_scope[m.office_id])
    for g in sorted(groups, key=lambda g: (g.sort_order, g.name)):
        members = sorted(groups[g], key=lambda o: tree_key(o, by_id))
        sets.append((f"group:{g.id}", g.name, members, True))
    return sets


def load(sc) -> DeckData:
    period = sc.period
    results = read.get_agency_results(period)
    profile = read.period_profile(period, results)
    with_result = [o for o in sc.offices if (str(o.id), sc.view) in results]
    ids = {o.id for o in with_result}
    children: dict = {}
    for o in with_result:
        if o.parent_id in ids:
            children.setdefault(o.parent_id, []).append(o)
    starts = dict(period.fiscal_year.periods.values_list("month_index", "start_date"))
    data = DeckData(
        agency=Agency.objects.get(pk=period.agency_id),
        period=period,
        view=sc.view,
        final=period.status == ReportingPeriod.Status.LOCKED,
        profile=profile,
        results=results,
        offices=with_result,
        root=sc.root,
        month_labels=[MONTH_ABBR[starts[m].month - 1] for m in range(1, 13)],
        children=children,
        without_result=[o for o in sc.offices if o.id not in ids],
        scope_offices=sc.offices,
    )
    return data


def build(sc, *, groups=SLIDE_GROUPS, settings: dict | None = None, logo: bytes | None = None, user=None,
          layout=DEFAULT) -> tuple[bytes, dict]:  # fmt: skip
    """The deck for one export scope. Returns (file bytes, summary for the job result)."""
    from apps.exports.xlsx_writer import profile_text

    data = load(sc)
    deck = Deck(data, settings or {}, layout, logo)
    deck.title_slide()
    root_rv = data.rv(sc.root)
    if "overall" in groups and root_rv is not None:
        deck.office_slide(sc.root, "overall")
    if "offices" in groups:
        for office in data.offices:
            if office.id != sc.root.id or root_rv is None or "overall" not in groups:
                deck.office_slide(office, "office")
    if "rankings" in groups:
        deck.ranking_slides()
    if "indicators" in groups:
        deck.indicator_slides()
    deck.notes_slide(user, profile_text(data.profile))
    deck.footers()
    summary = {"slides": len(deck.prs.slides), "offices": len(data.offices), "map": deck.map.slides}
    return deck.save(), summary

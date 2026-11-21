"""Over-all performance deck for the year (the agency's year-end presentation).

Built from the same results as the dashboard, for one month ("as of"), usually the last month of
the year:

1. title — the deck's title (e.g. "Over-all performance"), "As of <last day of the month>";
2. over-all — two panels for the starting office: performance based on activities (plan, actual,
   gap, status, funds remaining, S-curve) and based on output indicators (target, achieved, gap,
   monthly line), with one small panel per office directly beneath;
3. for every office that has offices beneath it: one small panel per office beneath (continued
   over several slides when there are many);
4. for every office with its own plan: its dashboard, its activities month by month (dark =
   planned month, yellow = month with an accomplishment) and its indicators;
5. rankings by activities and by output indicators for each set of offices compared together;
6. a closing slide.
"""

import calendar
import io
import logging
from dataclasses import dataclass, field
from decimal import Decimal

from pptx.chart.data import CategoryChartData
from pptx.enum.chart import XL_CHART_TYPE, XL_LEGEND_POSITION, XL_TICK_LABEL_POSITION
from pptx.enum.text import PP_ALIGN
from pptx.util import Inches, Pt

from apps.exports.pptx_layout import DEFAULT, FONT, MAX_TABLE_ROWS, SLIDE_W
from apps.exports.pptx_writer import (
    Deck,
    _num,
    d,
    load,
    money,
    pct,
    ranking_sets,
    rgb,
)
from apps.exports.text_fit import fit
from apps.planning.models import Plan
from apps.reporting.models import ActivityActual
from apps.results import read
from apps.results.agency import IMPLEMENTING, OWNER
from apps.results.dashboard_api import rank_set
from apps.scoring import engine

DEFAULT_TITLE = "Over-all performance"
PANELS_PER_SLIDE = 6
CLOSING = "Thank you"
log = logging.getLogger(__name__)


@dataclass
class YearData:
    """Per-month indicator scores and per-office monthly activity grids, on top of DeckData."""

    indicator_series: dict = field(default_factory=dict)  # office id -> [score or None] months 1..m
    grids: dict = field(default_factory=dict)  # office id -> [(title, target, [(plan, actual)] * 12)]


def as_of(period) -> str:
    last = calendar.monthrange(period.end_date.year, period.end_date.month)[1]
    return f"As of {period.end_date.strftime('%B')} {last}, {period.end_date.year}"


class YearDeck(Deck):
    def __init__(self, data, settings, title, layout=DEFAULT, logo=None):
        super().__init__(data, settings, layout, logo)
        self.title = title
        self.year = YearData()

    # ---- data ----
    def read_year(self):
        data = self.data
        month = data.period.month_index
        periods = {p.month_index: p for p in data.period.fiscal_year.periods.all()}
        ids = [str(o.id) for o in data.scope_offices]
        series = {oid: [None] * month for oid in ids}
        for m in range(1, month + 1):
            results = data.results if m == month else read.get_agency_results(periods[m])
            for oid in ids:
                rv = results.get((oid, data.view)) or results.get((oid, OWNER))
                if rv is not None and rv.indicator_score is not None:
                    series[oid][m - 1] = Decimal(str(rv.indicator_score))
        self.year.indicator_series = series
        plans = Plan.objects.filter(
            fiscal_year=data.period.fiscal_year,
            status=Plan.Status.APPROVED,
            office_id__in=[o.id for o in data.offices],
        )
        for plan in plans:
            rows = list(
                plan.rows.filter(row_kind="activity")
                .prefetch_related("targets__period")
                .order_by("sort_order")
            )
            done: dict = {}
            for a in ActivityActual.objects.filter(
                activity_lineage_id__in=[r.lineage_id for r in rows],
                period__fiscal_year=plan.fiscal_year,
                period__month_index__lte=month,
            ).select_related("period"):
                done[(a.activity_lineage_id, a.period.month_index)] = a.actual_qty
            grid = []
            for r in rows:
                planned = {t.period.month_index: t.planned_qty for t in r.targets.all()}
                cells = [
                    (planned.get(m, Decimal(0)), done.get((r.lineage_id, m)) if m <= month else None)
                    for m in range(1, 13)
                ]
                grid.append((f"{r.code} {r.title}".strip(), r.annual_target, cells))
            self.year.grids[str(plan.office_id)] = grid

    def score(self, office) -> Decimal | None:
        values = self.year.indicator_series.get(str(office.id)) or []
        return values[-1] if values else None

    def status_of(self, variance) -> tuple[str, str]:
        """(label, kind) for a gap, using the year's scoring labels."""
        if variance is None:
            return "—", "on_time"
        p = self.data.profile
        kind = engine.status_kind(Decimal(str(variance)), p)
        return engine.status(Decimal(str(variance)), p), kind

    # ---- pieces ----
    def tile(self, slide, x, y, w, h, label, value, kind, name):
        colors = {**self.L.tile_colors, **self.L.status_colors}
        bg, fg = colors.get(kind, colors["on_time"])
        self.text(
            slide,
            (Inches(x), Inches(y), Inches(w), Inches(h)),
            [(label, Pt(10)), value],
            Pt(18),
            bold=True,
            color=fg,
            fill=bg,
            align=PP_ALIGN.CENTER,
            name=name,
        )

    def panel_title(self, slide, x, y, w, text, name):
        self.text(
            slide,
            (Inches(x), Inches(y), Inches(w), Inches(0.38)),
            text.upper(),
            Pt(13),
            bold=True,
            color="FFFFFF",
            fill=self.s["primary_color"],
            align=PP_ALIGN.CENTER,
            name=name,
        )

    def curve(self, slide, box, title, series, name, *, percent_axis=True):
        """Line chart over the year's months; ``series`` = [(label, values, colour)]."""
        cd = CategoryChartData(number_format="0.00%")
        cd.categories = self.data.month_labels
        for label, values, _ in series:
            points = [None if v is None else float(v) for v in values]
            cd.add_series(label, points + [None] * (12 - len(points)))
        frame = slide.shapes.add_chart(XL_CHART_TYPE.LINE_MARKERS, *box, cd)
        frame.name = name
        chart = frame.chart
        chart.font.size = Pt(9)
        chart.font.name = FONT
        chart.has_title = True
        chart.chart_title.text_frame.text = title
        chart.chart_title.text_frame.paragraphs[0].runs[0].font.size = Pt(11)
        chart.has_legend = True
        chart.legend.position = XL_LEGEND_POSITION.BOTTOM
        chart.legend.include_in_layout = False
        if percent_axis:
            chart.value_axis.tick_labels.number_format = "0%"
            chart.value_axis.tick_labels.number_format_is_linked = False
        chart.value_axis.has_major_gridlines = True
        chart.category_axis.tick_label_position = XL_TICK_LABEL_POSITION.LOW  # below negative gaps
        for s, (_, _, color) in zip(chart.plots[0].series, series, strict=True):
            s.format.line.color.rgb = rgb(color)
            s.format.line.width = Pt(2.25)
            s.marker.format.fill.solid()
            s.marker.format.fill.fore_color.rgb = rgb(color)
            s.smooth = False

    def activity_series(self, rv):
        month = self.data.period.month_index
        plan = [d(v) for v in rv.series.get("cum_plan", [])][:12]
        actual = [d(v) for v in rv.series.get("cum_actual", [])][:month]
        gap = [a - p for a, p in zip(actual, plan, strict=False)]
        return [
            ("Plan (total so far)", plan, self.s["primary_color"]),
            ("Actual (total so far)", actual, self.s["actual_color"]),
            ("Gap", gap, "C0392B"),
        ]

    def mini_panel(self, slide, x, y, w, h, office, name):
        """One office in a small box: name, plan / actual / gap, status, funds remaining, indicators."""
        rv = self.data.rv(office)
        self.text(
            slide,
            (Inches(x), Inches(y), Inches(w), Inches(0.36)),
            office.name.upper(),
            Pt(11),
            bold=True,
            color="FFFFFF",
            fill=self.s["primary_color"],
            align=PP_ALIGN.CENTER,
            name=f"{name}-title",
        )
        if rv is None:
            self.text(
                slide,
                (Inches(x), Inches(y + 0.36), Inches(w), Inches(h - 0.36)),
                "No result yet",
                Pt(12),
                color="5B6878",
                fill="F4F6F9",
                align=PP_ALIGN.CENTER,
                name=f"{name}-body",
            )
            return
        label, kind = rv.status_label, rv.status_kind
        h_line = read.headline_of(rv)
        total = d(h_line["funds_total"]) or Decimal(0)
        remaining = d(h_line["funds_remaining"]) or Decimal(0)
        share = remaining / total if total else None
        score = self.score(office)
        big = h > 2
        lines = [
            (
                f"Plan {pct(rv.cum_plan)}   Actual {pct(rv.cum_actual)}   Gap {pct(rv.variance)}",
                Pt(14 if big else 11),
            ),
            (label, Pt(24 if big else 16)),
            (
                f"Funds remaining {pct(share)} ({money(remaining, self.s['currency_symbol'])})",
                Pt(12 if big else 10),
            ),
            (f"Output indicators {pct(score) if score is not None else '—'}", Pt(12 if big else 10)),
        ]
        bg, fg = self.L.status_colors.get(kind, self.L.status_colors["on_time"])
        self.text(
            slide,
            (Inches(x), Inches(y + 0.36), Inches(w), Inches(h - 0.36)),
            lines,
            Pt(11),
            bold=True,
            color=fg,
            fill=bg,
            align=PP_ALIGN.CENTER,
            name=f"{name}-body",
        )

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
            (data.agency.name, Pt(24), False, "1B2430"),
            (self.title.upper(), Pt(40), True, self.s["primary_color"]),
            (as_of(data.period).upper(), Pt(22), True, "1B2430"),
            ("FINAL" if data.final else "PROVISIONAL — the month is still open", Pt(14), False, "5B6878"),
        ]
        for top, (text, size, bold, color) in zip(L.title_lines, rows, strict=True):
            self.text(
                slide,
                (Inches(L.margin), Inches(top), width, Inches(0.8)),
                text,
                size,
                bold=bold,
                color=color,
                align=PP_ALIGN.CENTER,
                name="title-text",
            )

    def overall_slide(self, office):
        rv = self.data.rv(office)
        slide = self.new_slide("year_overall", str(office.id))
        self.header(slide, self.title if office.parent_id is None else f"{office.name} · {self.title}")
        left, right, top, w = 0.4, 6.78, 1.05, 6.15
        # Activities (PPAs)
        self.panel_title(slide, left, top, w, "Based on activities (PPAs)", "panel-activities")
        tw = (w - 0.3) / 4
        tiles = [
            ("PLAN", pct(rv.cum_plan), "plan"),
            ("ACTUAL", pct(rv.cum_actual), "actual"),
            ("GAP", pct(rv.variance), "variance"),
            ("STATUS", rv.status_label, rv.status_kind),
        ]
        for i, (label, value, kind) in enumerate(tiles):
            self.tile(
                slide,
                left + i * (tw + 0.1),
                top + 0.45,
                tw,
                0.8,
                label,
                value,
                kind,
                f"activities-{label.lower()}",
            )
        h_line = read.headline_of(rv)
        total, remaining = d(h_line["funds_total"]) or Decimal(0), d(h_line["funds_remaining"]) or Decimal(0)
        share = remaining / total if total else None
        sym = self.s["currency_symbol"]
        self.text(
            slide,
            (Inches(left), Inches(top + 1.3), Inches(w), Inches(0.36)),
            f"Funds remaining {pct(share)} ({money(remaining, sym)} of {money(total, sym)})",
            Pt(12),
            bold=True,
            color="1B2430",
            fill="F4F6F9",
            align=PP_ALIGN.CENTER,
            name="funds-remaining",
        )
        box = (Inches(left), Inches(top + 1.72), Inches(w), Inches(2.85))
        self.curve(slide, box, "S-curve based on activities", self.activity_series(rv), "chart-activities")
        # Output indicators
        self.panel_title(slide, right, top, w, "Based on output indicators", "panel-indicators")
        score = self.score(office)
        gap = (score - 1) if score is not None else None
        label, kind = self.status_of(gap) if gap is not None else ("—", "on_time")
        tiles = [
            ("TARGET", "100.00%", "plan"),
            ("ACHIEVED", pct(score), "actual"),
            ("GAP", pct(gap), "variance"),
            ("STATUS", label, kind),
        ]
        for i, (lab, value, k) in enumerate(tiles):
            self.tile(
                slide, right + i * (tw + 0.1), top + 0.45, tw, 0.8, lab, value, k, f"indicators-{lab.lower()}"
            )
        self.text(
            slide,
            (Inches(right), Inches(top + 1.3), Inches(w), Inches(0.36)),
            "Share of the year's output targets reached so far",
            Pt(12),
            color="1B2430",
            fill="F4F6F9",
            align=PP_ALIGN.CENTER,
            name="indicators-note",
        )
        values = self.year.indicator_series.get(str(office.id)) or []
        box = (Inches(right), Inches(top + 1.72), Inches(w), Inches(2.85))
        if all(v is None for v in values):
            self.text(
                slide,
                box,
                "No output indicators recorded yet",
                Pt(14),
                color="5B6878",
                fill="F4F6F9",
                align=PP_ALIGN.CENTER,
                name="chart-indicators",
            )
            values = None
        if values is not None:
            self.curve(
                slide,
                box,
                "Output indicators reached, month by month",
                [("Reached (share of year target)", values, self.s["actual_color"])],
                "chart-indicators",
            )
        # One small panel per office directly beneath
        kids = self.data.children.get(office.id, [])[:PANELS_PER_SLIDE]
        if kids:
            n = len(kids)
            gap_x = 0.12
            pw = (12.53 - gap_x * (n - 1)) / n
            for i, kid in enumerate(kids):
                self.mini_panel(slide, 0.4 + i * (pw + gap_x), 5.68, pw, 1.27, kid, f"child-{i}")

    def group_slides(self, office):
        kids = self.data.children.get(office.id, [])
        chunks = [kids[i : i + PANELS_PER_SLIDE] for i in range(0, len(kids), PANELS_PER_SLIDE)]
        for n, chunk in enumerate(chunks):
            slide = self.new_slide("year_group", str(office.id))
            self.header(slide, f"{office.name} · offices beneath", "(continued)" if n else "")
            cols, pw, ph = 3, (12.53 - 0.3) / 3, 2.75
            for i, kid in enumerate(chunk):
                r, c = divmod(i, cols)
                self.mini_panel(
                    slide, 0.4 + c * (pw + 0.15), 1.1 + r * (ph + 0.15), pw, ph, kid, f"panel-{i}"
                )

    def grid_slides(self, office):
        grid = self.year.grids.get(str(office.id)) or []
        if not grid:
            return
        L = self.L
        per = MAX_TABLE_ROWS
        chunks = [grid[i : i + per] for i in range(0, len(grid), per)]
        headers = ["Activity", "Target", *self.data.month_labels]
        for n, chunk in enumerate(chunks):
            slide = self.new_slide("year_activities", str(office.id))
            self.header(slide, f"{office.name} · activities by month", "(continued)" if n else "")
            x, y, w, _ = L.table.emu()
            shape = slide.shapes.add_table(
                len(chunk) + 1, len(headers), x, y, w, Inches(0.36) * (len(chunk) + 1)
            )
            shape.name = "table-year-activities"
            table = shape.table
            widths = [4.4, 1.0] + [0.594] * 12
            for c, frac in enumerate(widths):
                table.columns[c].width = int(w * frac / sum(widths))
            for r, row in enumerate([None, *chunk]):
                for c in range(len(headers)):
                    cell = table.cell(r, c)
                    fill, color, value = None, "1B2430", ""
                    if r == 0:
                        value, fill, color = headers[c], self.s["primary_color"], "FFFFFF"
                    elif c == 0:
                        value = row[0]
                    elif c == 1:
                        value = _num(row[1])
                    else:
                        plan, actual = row[2][c - 2]
                        if actual is not None and actual > 0:
                            value, fill = _num(actual), self.s["accent_color"]
                        elif plan and plan > 0:
                            value, fill, color = _num(plan), self.s["primary_color"], "FFFFFF"
                    width_pt = table.columns[c].width / 12700 - 10
                    cell.text = fit(str(value), width_pt, 10, bold=(r == 0))
                    cell.margin_left = cell.margin_right = Inches(0.03)
                    para = cell.text_frame.paragraphs[0]
                    para.alignment = PP_ALIGN.LEFT if c == 0 else PP_ALIGN.CENTER
                    for run in para.runs:
                        run.font.size = Pt(10)
                        run.font.name = FONT
                        run.font.bold = r == 0
                        run.font.color.rgb = rgb(color)
                    if fill:
                        cell.fill.solid()
                        cell.fill.fore_color.rgb = rgb(fill)
                    elif r:
                        cell.fill.solid()
                        cell.fill.fore_color.rgb = rgb("FFFFFF")
            self.text(
                slide,
                (Inches(0.4), Inches(6.55), Inches(12.53), Inches(0.35)),
                "Dark cell: month the activity was planned (planned number). "
                "Yellow cell: month with an accomplishment (number done).",
                Pt(10),
                color="5B6878",
                name="grid-legend",
            )

    def office_indicator_slides(self, office):
        full = read.get_result(self.data.period, office, self.data.view)
        inds = full.indicators if full else []
        if not inds:
            return
        rows = [
            [
                f"{i.get('code') or ''} {i['name']}".strip(),
                _num(i["annual_target"]),
                _num(i["actual_to_date"]),
                pct(i["rate"]),
            ]
            for i in inds
        ]
        self.table_slides(
            "indicators",
            str(office.id),
            f"{office.name} · output indicators",
            ["Output indicator", "Year target", "Done so far", "Reached"],
            rows,
            [7, 2, 2, 1.5],
            [PP_ALIGN.LEFT, PP_ALIGN.RIGHT, PP_ALIGN.RIGHT, PP_ALIGN.RIGHT],
        )

    def indicator_ranking_rows(self, members):
        scored = sorted(
            ((m, self.score(m)) for m in members), key=lambda t: (t[1] is None, -(t[1] or 0), t[0].name)
        )
        rows, rank, prev = [], 0, object()
        for i, (m, s) in enumerate(scored, start=1):
            if s is None:
                rows.append(["—", f"{m.code} {m.name}", "No indicators", "—"])
                continue
            if s != prev:
                rank, prev = i, s
            label, _ = self.status_of(s - 1)
            rows.append([rank, f"{m.code} {m.name}", pct(s), label])
        return rows

    def year_ranking_slides(self):
        data = self.data
        month = data.period.month_index
        for key, name, members, allow_impl in ranking_sets(data):
            ranked = rank_set(
                data.results, [str(m.id) for m in members], data.profile, month, allow_implementing=allow_impl
            )
            by_id = {str(o.id): o for o in members}
            rows = []
            for office_id, rank, _value in ranked:
                o = by_id[office_id]
                rv = data.results.get((office_id, OWNER)) or (
                    data.results.get((office_id, IMPLEMENTING)) if allow_impl else None
                )
                rows.append(
                    [
                        rank or "—",
                        f"{o.code} {o.name}",
                        pct(rv.cum_actual) if rv else "No result",
                        rv.status_label if rv else "—",
                    ]
                )
            aligns = [PP_ALIGN.CENTER, PP_ALIGN.LEFT, PP_ALIGN.RIGHT, PP_ALIGN.CENTER]
            if any(r[0] != "—" for r in rows):  # skip sets where nobody has a result yet
                self.table_slides(
                    "ranking_activities",
                    key,
                    f"Ranking based on activities · {name}",
                    ["Rank", "Office", "Actual (total so far)", "Status"],
                    rows,
                    [0.8, 7.5, 2.4, 1.8],
                    aligns,
                )
            ind_rows = self.indicator_ranking_rows(members)
            if any(r[0] != "—" for r in ind_rows):
                self.table_slides(
                    "ranking_indicators",
                    key,
                    f"Ranking based on output indicators · {name}",
                    ["Rank", "Office", "Output targets reached", "Status"],
                    ind_rows,
                    [0.8, 7.5, 2.4, 1.8],
                    aligns,
                )

    def closing_slide(self):
        slide = self.new_slide("closing")
        self.text(
            slide,
            (Inches(0.4), Inches(2.8), Inches(12.53), Inches(1.4)),
            CLOSING.upper(),
            Pt(54),
            bold=True,
            color=self.s["primary_color"],
            align=PP_ALIGN.CENTER,
            name="closing-text",
        )


def build(sc, *, title: str = "", settings: dict | None = None, logo: bytes | None = None, user=None):
    """The year's over-all performance deck for one export scope. Returns (bytes, summary)."""
    data = load(sc)
    deck = YearDeck(data, settings or {}, (title or "").strip() or DEFAULT_TITLE, DEFAULT, logo)
    deck.read_year()
    deck.title_slide()
    if data.rv(sc.root) is not None:
        deck.overall_slide(sc.root)
    for office in data.offices:
        if office.id != sc.root.id and data.children.get(office.id):
            deck.group_slides(office)
    if sc.root.id in data.children and data.rv(sc.root) is None:
        deck.group_slides(sc.root)
    for office in data.offices:
        if str(office.id) in deck.year.grids:
            deck.office_slide(office, "office")
            deck.grid_slides(office)
            deck.office_indicator_slides(office)
    deck.year_ranking_slides()
    deck.closing_slide()
    deck.footers()
    summary = {"slides": len(deck.prs.slides), "offices": len(data.offices), "map": deck.map.slides}
    return deck.save(), summary

"""P10.4 and the Phase 10 exit check — the PowerPoint deck against the dashboard API.

* slide count and order for a known tree (the MOST sample agency, December);
* every chart's data equals the dashboard API's values;
* the deck opens with python-pptx (and, when installed, LibreOffice) without repair;
* long office names are cut with an ellipsis after measuring, never overflowing their box;
* a ranking slide's order follows the 8.2 ranking rule (the provincial vector).
"""

import io
import random
import uuid
from decimal import Decimal as D
from pathlib import Path

import pytest
from django.core.management import call_command
from pptx import Presentation

from apps.exports import pptx_writer
from apps.exports import scope as export_scope
from apps.exports.pptx_layout import DEFAULT as L
from apps.exports.text_fit import text_width
from apps.tenancy import context
from apps.tenancy.models import Agency
from tests import libreoffice
from tests.factories import Json, api_client

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures"
HAS_MOST = (FIXTURES / "most_fy2023_rdi.json").exists()
CLOSE = 1e-9


def build(agency_id, office, period_id, scope="agency", groups=pptx_writer.SLIDE_GROUPS):
    with context.agency_context(agency_id):
        sc = export_scope.resolve(
            {"scope": scope, "office_id": str(office.id), "period_id": str(period_id), "view": "owner"}
        )
        data, summary = pptx_writer.build(sc, groups=groups)
    return data, summary, sc


def named(slide) -> dict:
    return {s.name: s for s in slide.shapes}


def table_rows(slide) -> list:
    table = next(s for s in slide.shapes if s.has_table).table
    return [[c.text for c in row.cells] for row in list(table.rows)[1:]]


@pytest.fixture
def most(django_db_blocker):
    call_command("seed_demo")
    from apps.planning.models import ReportingPeriod
    from apps.structure.models import Office

    agency = Agency.objects.using("owner").get(code="sample-ministry")
    with context.agency_context(agency.id):
        root = Office.objects.get(parent=None)
        december = ReportingPeriod.objects.get(fiscal_year__label="2023", month_index=12)
        offices = {o.code: o for o in Office.objects.all()}
    api = Json(api_client("admin@sample-ministry.demo", "demo-password-2026"))
    return {"agency": agency, "root": root, "december": december, "offices": offices, "api": api}


@pytest.mark.skipif(not HAS_MOST, reason="P4.2 fixtures missing")
@pytest.mark.django_db(databases=["default", "owner"], transaction=True)
def test_most_december_deck_matches_the_dashboard(most, tmp_path):
    data, summary, sc = build(most["agency"].id, most["root"], most["december"].id)
    prs = Presentation(io.BytesIO(data))  # opens without repair
    kinds = summary["map"]
    o = most["offices"]

    # ---- Slide count and order (tree order; offices without a result are left out) ----
    office_slides = [key for kind, key in kinds if kind in ("overall", "office")]
    with_result = ["ODS", "PME", "HRM", "RDS", "RDI", "AST", "ILD", "FAS", "GAS"]  # FOS and centers: none
    assert office_slides == [str(most["root"].id)] + [str(o[c].id) for c in with_result]
    assert [k for k, _ in kinds][:2] == ["title", "overall"]
    assert [k for k, _ in kinds][-1] == "notes"
    rankings = [key for kind, key in kinds if kind == "ranking"]
    assert rankings[:3] == [
        f"children:{most['root'].id}",
        f"children:{o['ODS'].id}",
        f"children:{o['RDS'].id}",
    ]
    assert len(prs.slides) == len(kinds) == summary["slides"]
    for i, slide in enumerate(list(prs.slides)[1:], start=2):
        assert named(slide)["footer-page"].text_frame.text == f"Page {i} of {len(kinds)}"

    # ---- Every chart's data equals the dashboard API ----
    api, period = most["api"], most["december"].id
    for index, (kind, key) in enumerate(kinds):
        if kind not in ("overall", "office"):
            continue
        dash = api.get(f"/api/v1/dashboard?office={key}&period={period}").json()
        shapes = named(prs.slides[index])
        h = dash["headline"]
        curve = shapes["chart-scurve"].chart.plots[0]
        plan, actual = (list(s.values) for s in curve.series)
        assert plan == pytest.approx([float(v) for v in dash["series"]["cum_plan"]], abs=CLOSE)
        want_actual = [None if v is None else float(v) for v in dash["series"]["cum_actual"]]
        assert [None if v is None else round(v, 12) for v in actual] == [
            None if v is None else round(v, 12) for v in want_actual
        ]
        funds = list(shapes["chart-funds"].chart.plots[0].series[0].values)
        used = h["funds_used_actual"] if h["funds_used_actual"] is not None else h["funds_used_est"]
        assert funds == pytest.approx([float(used), max(float(h["funds_remaining"]), 0)], abs=0.005)
        assert shapes["tile-actual"].text_frame.text == f"ACTUAL\n{D(h['cum_actual']) * 100:,.2f}%"
        assert shapes["tile-status"].text_frame.text == f"STATUS\n{h['status']}"
        kids = [c for c in dash["children"] if c["result"] is not None]
        if kids:
            bars = shapes["chart-children"].chart.plots[0]
            assert list(bars.categories) == [c["office"]["code"] for c in kids]
            assert list(bars.series[1].values) == pytest.approx(
                [float(c["result"]["cum_actual"]) for c in kids], abs=CLOSE
            )
        else:
            assert "chart-children" not in shapes

    # ---- Phase exit: the RDS ranking slide follows the ranking rule (8.2: highest first) ----
    rds_index = next(i for i, (k, key) in enumerate(kinds) if key == f"children:{o['RDS'].id}")
    rows = table_rows(prs.slides[rds_index])
    assert [(r[0], r[1].split()[0], r[2]) for r in rows] == [
        ("1", "RDI", "99.07%"),
        ("2", "ILD", "90.23%"),
        ("3", "AST", "58.76%"),
    ]
    ranking = api.get(f"/api/v1/rankings?period={period}&set=children:{o['RDS'].id}").json()
    assert [r["office"]["code"] for r in ranking["rows"]] == ["RDI", "ILD", "AST"]

    # ---- Opens in LibreOffice too (when installed) ----
    if libreoffice.SOFFICE:
        path = tmp_path / "deck.pptx"
        path.write_bytes(data)
        import subprocess

        subprocess.run(  # noqa: S603 — fixed program, test-made path
            [libreoffice.SOFFICE, f"-env:UserInstallation={(tmp_path / 'lo').as_uri()}", "--headless",
             "--convert-to", "pdf", "--outdir", str(tmp_path), str(path)],
            check=True, capture_output=True, timeout=180,
        )  # fmt: skip
        assert (tmp_path / "deck.pdf").stat().st_size > 10_000


def _office_with_result(root, level, code, name, fy, periods, actual_ratio):
    """An office with one plan line: target 10,000 in December, actual = ratio × 10,000."""
    from apps.planning.models import Activity, ActivityTarget, Plan
    from apps.reporting.models import ActivityActual
    from apps.structure.models import Office

    office = Office.objects.create(
        parent=root, level=level, name=name, code=code, sort_order=random.randint(0, 99)
    )
    plan = Plan.objects.create(office=office, fiscal_year=fy, status="approved", version=1)
    act = Activity.objects.create(
        plan=plan, lineage_id=uuid.uuid4(), row_kind="activity", code=f"{code}-1", title="Services",
        measure_type="quantity", annual_target=D(10000), total_cost=D(1000), implementing_office=office,
    )  # fmt: skip
    ActivityTarget.objects.create(activity=act, period=periods[12], planned_qty=D(10000))
    ActivityActual.objects.create(
        activity_lineage_id=act.lineage_id,
        period=periods[12],
        office=office,
        actual_qty=D(actual_ratio) * 100,
    )
    return office


@pytest.mark.django_db
def test_ranking_slide_follows_the_provincial_ranking_vector():
    """8.2: values 96.27, 96.23, 96.18, 93.50, 87.74, 87.37, 76.57 → ranks 1–7 in that order, whatever
    the offices' order in the tree."""
    from apps.planning.services import create_fiscal_year, set_fiscal_year_status
    from apps.structure.models import OrgLevel
    from tests.factories import make_agency, make_root

    vector = [("P1", "96.27"), ("P2", "96.23"), ("P3", "96.18"), ("P4", "93.50"), ("P5", "87.74"),
              ("P6", "87.37"), ("P7", "76.57")]  # fmt: skip
    agency = make_agency("prov")
    root = make_root(agency)
    random.seed(3)
    with context.agency_context(agency.id):
        level = OrgLevel.objects.get_or_create(depth=1, defaults={"name": "Center"})[0]
        fy = create_fiscal_year("PROV", 2023)
        set_fiscal_year_status(fy, "open")
        periods = {p.month_index: p for p in fy.periods.all()}
        for code, value in reversed(vector):
            _office_with_result(root, level, code, f"Center {code}", fy, periods, value)
    data, summary, _ = build(agency.id, root, periods[12].id, groups=("rankings",))
    prs = Presentation(io.BytesIO(data))
    [index] = [i for i, (kind, _) in enumerate(summary["map"]) if kind == "ranking"]
    rows = table_rows(prs.slides[index])
    assert [(r[0], r[1].split()[0], r[2]) for r in rows] == [
        (str(i), code, f"{value}%") for i, (code, value) in enumerate(vector, start=1)
    ]


@pytest.mark.django_db
def test_long_office_names_are_cut_with_an_ellipsis_and_long_tables_continue():
    from tests.export_helpers import worked_example_world

    w = worked_example_world()
    long_name = ("Regional Office for Science and Technology Services of the Autonomous Region " * 3)[:200]
    with context.agency_context(w["agency"].id):
        w["div"].name = long_name.strip()
        w["div"].save()
    data, summary, _ = build(w["agency"].id, w["root"], w["periods"][3]["id"])
    prs = Presentation(io.BytesIO(data))
    index = [k for k, _ in summary["map"]].index("office")
    title = named(prs.slides[index])["header-title"]
    text = title.text_frame.text
    assert text.endswith("…") and len(text) < len(long_name)
    run = title.text_frame.paragraphs[0].runs[0]
    assert text_width(text, run.font.size.pt, bold=True) <= title.width / 12700
    ranking = [i for i, (k, _) in enumerate(summary["map"]) if k == "ranking"][0]
    cell = next(s for s in prs.slides[ranking].shapes if s.has_table).table.cell(1, 1)
    assert cell.text.endswith("…")


@pytest.mark.django_db
def test_tables_longer_than_twelve_rows_continue_on_the_next_slide():
    from apps.exports.pptx_layout import MAX_TABLE_ROWS
    from apps.planning.services import create_fiscal_year, set_fiscal_year_status
    from apps.structure.models import OrgLevel
    from tests.factories import make_agency, make_root

    agency = make_agency("many")
    root = make_root(agency)
    with context.agency_context(agency.id):
        level = OrgLevel.objects.get_or_create(depth=1, defaults={"name": "Unit"})[0]
        fy = create_fiscal_year("MANY", 2023)
        set_fiscal_year_status(fy, "open")
        periods = {p.month_index: p for p in fy.periods.all()}
        for i in range(MAX_TABLE_ROWS + 3):
            _office_with_result(root, level, f"U{i:02d}", f"Unit {i}", fy, periods, str(50 + i))
    data, summary, _ = build(agency.id, root, periods[12].id, groups=("rankings",))
    prs = Presentation(io.BytesIO(data))
    slides = [i for i, (k, _) in enumerate(summary["map"]) if k == "ranking"]
    assert len(slides) == 2
    assert len(table_rows(prs.slides[slides[0]])) == MAX_TABLE_ROWS
    assert len(table_rows(prs.slides[slides[1]])) == 3
    assert named(prs.slides[slides[1]])["header-title"].text_frame.text.endswith("(CONTINUED)")
    assert L.table.w > 0

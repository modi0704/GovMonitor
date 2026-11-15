"""P9.5 — MASTERPLAN 9.3: recalculating the exported workbook gives the dashboard's cumulative
percentages (±0.005 points) for the same month. The formulas are recomputed from the cell inputs
by a small evaluator (cached results ignored) and, when LibreOffice is installed, by LibreOffice."""

from decimal import Decimal as D

import openpyxl
import pytest

from apps.exports.layout import DEFAULT as L
from tests import libreoffice
from tests.export_helpers import FIXTURES, build, rdi_world, worked_example_world
from tests.xlsx_eval import Evaluator

pytestmark = pytest.mark.django_db
TOLERANCE = D("0.00005")  # 0.005 percentage points


def total_row(ws) -> int:
    return next(r for r in range(8, ws.max_row + 1) if ws[f"H{r}"].value == L.total_label)


def figures_from_formulas(data, sheet: str, month: int) -> tuple[D, D]:
    ev = Evaluator(data)
    t = total_row(ev.wb[sheet])
    col = L.weighted_cols[month - 1]
    return ev.number(sheet, f"{col}{t + 2}"), ev.number(sheet, f"{col}{t + 4}")


def dashboard(api, office, period_id) -> tuple[D, D]:
    h = api.get(f"/api/v1/dashboard?office={office.id}&period={period_id}").json()["headline"]
    return D(h["cum_plan"]), D(h["cum_actual"])


@pytest.mark.parametrize("month", [1, 2, 3])
def test_worked_example_formulas_give_the_dashboard_figures(month):
    w = worked_example_world()
    pid = w["periods"][month]["id"]
    data, _ = build(w["agency"], w["div"], pid)
    plan, actual = figures_from_formulas(data, "DIV", month)
    want_plan, want_actual = dashboard(w["boss"], w["div"], pid)
    assert abs(plan - want_plan) <= TOLERANCE and abs(actual - want_actual) <= TOLERANCE
    assert actual == {1: D("0.12"), 2: D("0.315"), 3: D("0.78")}[month]


@pytest.mark.skipif(not (FIXTURES / "most_fy2023_rdi.json").exists(), reason="P4.2 fixtures missing")
@pytest.mark.parametrize("month", [6, 12])
def test_rdi_fixture_formulas_give_the_dashboard_figures(month):
    w = rdi_world()
    pid = w["periods"][month]["id"]
    data, _ = build(w["agency"], w["rdi"], pid)
    plan, actual = figures_from_formulas(data, "RDI", month)
    want_plan, want_actual = dashboard(w["api"], w["rdi"], pid)
    assert abs(plan - want_plan) <= TOLERANCE and abs(actual - want_actual) <= TOLERANCE
    if month == 12:
        assert abs(actual - D("0.9907")) <= TOLERANCE  # MASTERPLAN 8.2


@pytest.mark.skipif(libreoffice.SOFFICE is None, reason="LibreOffice is not installed")
@pytest.mark.skipif(not (FIXTURES / "most_fy2023_rdi.json").exists(), reason="P4.2 fixtures missing")
def test_libreoffice_recalculation_gives_the_dashboard_figures(tmp_path):
    worked = worked_example_world()
    rdi = rdi_world()
    cases = [
        (worked, worked["div"], "DIV", 3, worked["boss"]),
        (rdi, rdi["rdi"], "RDI", 12, rdi["api"]),
    ]
    files = []
    for i, (w, office, _sheet, month, _api) in enumerate(cases):
        data, _ = build(w["agency"], office, w["periods"][month]["id"])
        # Overwrite every cached result so only LibreOffice's own calculation can be right.
        path = tmp_path / f"case{i}.xlsx"
        path.write_bytes(_poison_cached_values(data.getvalue()))
        files.append(path)
    for path, (w, office, sheet, month, api) in zip(
        libreoffice.recalculate(files, tmp_path), cases, strict=True
    ):
        ws = openpyxl.load_workbook(path, data_only=True)[sheet]
        t = total_row(ws)
        col = L.weighted_cols[month - 1]
        want_plan, want_actual = dashboard(api, office, w["periods"][month]["id"])
        assert abs(D(str(ws[f"{col}{t + 2}"].value)) - want_plan) <= TOLERANCE
        assert abs(D(str(ws[f"{col}{t + 4}"].value)) - want_actual) <= TOLERANCE
        funds_used = D(str(ws[f"W{t + 9}"].value))
        assert abs(funds_used - want_actual * D(str(ws[f"W{t + 8}"].value))) <= D("0.01")


def _poison_cached_values(xlsx: bytes) -> bytes:
    import io
    import re
    import zipfile

    src = zipfile.ZipFile(io.BytesIO(xlsx))
    out = io.BytesIO()
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as dst:
        for item in src.infolist():
            content = src.read(item.filename)
            if item.filename.startswith("xl/worksheets/"):
                content = re.sub(rb"(</f>)<v>[^<]*</v>", rb"\1<v>999</v>", content)
            dst.writestr(item, content)
    return out.getvalue()

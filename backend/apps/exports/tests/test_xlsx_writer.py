"""P9.2: the office sheet of the Excel export (MASTERPLAN 9.1) on the 8.1 worked example."""

import openpyxl
import pytest

from apps.exports.xlsx_writer import sheet_name
from tests.export_helpers import build, worked_example_world

pytestmark = pytest.mark.django_db


def sheet(w, month=3, **kw):
    data, _ = build(w["agency"], w["div"], w["periods"][month]["id"], **kw)
    return openpyxl.load_workbook(data)


def cached(w, month=3):
    data, _ = build(w["agency"], w["div"], w["periods"][month]["id"])
    return openpyxl.load_workbook(data, data_only=True)["DIV"]


def test_title_block_rows_and_markers():
    w = worked_example_world()
    wb = sheet(w)
    assert wb.sheetnames == ["SUMMARY", "DIV"]
    ws = wb["DIV"]
    assert ws["A1"].value == "Fiscal Year 2026"
    assert ws["A3"].value == "DIV" and ws["A4"].value == "As of March 2026"
    assert ws["A8"].value == "DIV" and ws["D8"].value == "O1 Output one"  # output → column D
    assert [ws[f"N{r}"].value for r in range(9, 15)] == ["PLAN", "ACTUAL"] * 3
    assert ws["H9"].value == "A Activity A" and ws["I9"].value == 10 and ws["L9"].value == 600000
    assert ws["M9"].value == "=L9/$L$15"
    assert ws["AD9"].value == "=O9*$M9/$I9" and ws["AO10"].value == "=Z10*$M9/$I9"
    assert ws["L15"].value == "=SUM(L8:L14)" and ws["B15"].value == ws["H15"].value == "TOTAL COST"
    assert ws["W26"].value == "DELAYED"
    assert ws.freeze_panes == "O8"
    assert all(ws[f"{c}{r}"].value is None for c in ("AA", "AB", "AC") for r in range(1, ws.max_row + 1))


def test_actuals_stop_at_the_selected_month_and_cached_values_match_the_engine():
    w = worked_example_world()
    ws = sheet(w, month=2)["DIV"]
    assert ws["P10"].value == 2 and ws["Q10"].value is None  # March actual not shown in February
    assert ws["W24"].value == "=AE19*W23"  # funds used from February's cumulative actual
    values = cached(w)
    assert [round(values[c].value, 6) for c in ("AD17", "AE17", "AF17")] == [0.12, 0.45, 1.0]
    assert [round(values[c].value, 6) for c in ("AD19", "AE19", "AF19")] == [0.12, 0.315, 0.78]
    assert values["W24"].value == pytest.approx(780000) and values["W25"].value == pytest.approx(220000)
    assert values["M9"].value == pytest.approx(0.6)


def test_non_default_profile_writes_engine_values_in_the_total_rows():
    w = worked_example_world(profile={"preset": "capped_with_tolerance"})
    ws = sheet(w)["DIV"]
    assert isinstance(ws["AF19"].value, float) and ws["AF19"].value == pytest.approx(0.78)
    assert ws["AD16"].comment is not None
    assert ws["AD9"].value == "=O9*$M9/$I9"  # per-activity cells keep their formulas


def test_equal_weights_are_written_as_values():
    w = worked_example_world(profile={"weighting": "equal"})
    ws = sheet(w)["DIV"]
    assert ws["M9"].value == pytest.approx(1 / 3)


def test_recurring_measure_cells_are_engine_values_with_a_comment():
    w = worked_example_world()
    plan = w["boss"].get(f"/api/v1/plans/{w['plan']['id']}").json()
    # Revise so that activity C becomes a recurring measure in a new approved version.
    rev = w["boss"].post(f"/api/v1/plans/{plan['id']}/revise").json()
    rows = w["boss"].get(f"/api/v1/plans/{rev['id']}").json()["rows"]
    for r in rows:
        r["client_key"] = r["id"]
        r["parent"] = r.get("parent_id")
        if r.get("code") == "C":
            r["measure_type"] = "recurring"
            r["targets"] = ["1"] * 12
    saved = w["boss"].post(f"/api/v1/plans/{rev['id']}/save", {"rows": rows})
    assert saved.status_code == 200, saved.content
    w["boss"].post(f"/api/v1/plans/{rev['id']}/submit")
    assert w["boss"].post(f"/api/v1/plans/{rev['id']}/approve").status_code == 200
    ws = sheet(w)["DIV"]
    assert isinstance(ws["AD13"].value, float)
    assert ws["AD13"].comment.text.startswith("Recurring measure")


def test_sheet_names_are_valid_and_unique():
    used = {"SUMMARY"}
    assert sheet_name("A/B", used) == "A-B"
    assert sheet_name("a-b", used) == "a-b-2"
    assert sheet_name("summary", used) == "summary-2"
    assert len(sheet_name("X" * 40, used)) == 31

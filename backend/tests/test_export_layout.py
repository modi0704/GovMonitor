"""P9.6 — the RDI fixture's office sheet checked cell by cell against MASTERPLAN 9.1: header rows
5–7, the column of every field, the PLAN/ACTUAL pairing, and the formulas of the first activity
and of the total rows."""

import openpyxl
import pytest
from openpyxl.utils import get_column_letter

from tests.export_helpers import FIXTURES, OUTLINE_KINDS, build, rdi_world

pytestmark = [
    pytest.mark.django_db,
    pytest.mark.skipif(not (FIXTURES / "most_fy2023_rdi.json").exists(), reason="P4.2 fixtures missing"),
]

MONTHS = [get_column_letter(c) for c in range(15, 27)]  # O..Z
WEIGHTED = [get_column_letter(c) for c in range(30, 42)]  # AD..AO
ABBR = ["JAN", "FEB", "MAR", "APR", "MAY", "JUN", "JUL", "AUG", "SEP", "OCT", "NOV", "DEC"]
FULL = ["JANUARY", "FEBRUARY", "MARCH", "APRIL", "MAY", "JUNE", "JULY", "AUGUST", "SEPTEMBER", "OCTOBER",
        "NOVEMBER", "DECEMBER"]  # fmt: skip


@pytest.fixture
def world():
    w = rdi_world(outline=True)
    data, _ = build(w["agency"], w["rdi"], w["periods"][12]["id"])
    return w, openpyxl.load_workbook(data)


def test_rdi_office_sheet_layout(world):
    w, wb = world
    ws = wb["RDI"]
    acts = [r for r in w["rows"] if r["row_kind"] == "activity"]
    n = len(acts)
    first_act = 8 + len(OUTLINE_KINDS)
    t = first_act + 2 * n

    # ---- Title block and header rows 5–7 ----
    assert ws["A1"].value == "Fiscal Year 2023"
    assert ws["A2"].value == w["agency"].name and ws["A3"].value == w["rdi"].name
    assert ws["A4"].value == "As of December 2023"
    expected_5 = {"A5": "AGENCY", "B5": "OUTCOME STATEMENT", "C5": "OUTCOME INDICATORS", "D5": "OUTPUTS",
                  "E5": "OUTPUT INDICATORS", "F5": "PROGRAMS", "G5": "PROJECTS", "H5": "ACTIVITIES",
                  "I5": "TARGETS", "K5": "PROJECTED COST",
                  "O5": "INDICATIVE SCHEDULE OF IMPLEMENTATION (MONTHLY)",
                  "AD5": "INDICATIVE SCHEDULE OF IMPLEMENTATION (MONTHLY)"}  # fmt: skip
    for cell, text in expected_5.items():
        assert ws[cell].value == text, cell
    for cell, text in {"O6": "Q1", "R6": "Q2", "U6": "Q3", "X6": "Q4", "AD6": "Q1", "AG6": "Q2", "AJ6": "Q3",
                       "AM6": "Q4"}.items():  # fmt: skip
        assert ws[cell].value == text, cell
    row7 = {"I7": "QTY", "J7": "UNIT", "K7": "UNIT COST", "L7": "TOTAL COST", "M7": "Wtd%", "N7": "REMARKS"}
    for cell, text in row7.items():
        assert ws[cell].value == text, cell
    assert [ws[f"{c}7"].value for c in MONTHS] == ABBR
    assert [ws[f"{c}7"].value for c in WEIGHTED] == ABBR
    merged = {str(m) for m in ws.merged_cells.ranges}
    must_merge = {"I5:J6", "K5:L6", "O5:Z5", "AD5:AO5", "O6:Q6", "R6:T6", "U6:W6", "X6:Z6", "AD6:AF6",
                  "AG6:AI6", "AJ6:AL6", "AM6:AO6", *(f"{c}5:{c}7" for c in "ABCDEFGH")}  # fmt: skip
    assert must_merge <= merged, must_merge - merged
    assert ws["A5"].font.b and ws["A5"].fill.fgColor.rgb.endswith("FFD965")

    # ---- Outline rows: one row each, in the column of its kind ----
    assert ws["A8"].value == w["rdi"].name.upper()
    for i, (kind, col) in enumerate(zip(OUTLINE_KINDS, "BCDEFG", strict=True)):
        r = 8 + i
        assert ws[f"{col}{r}"].value == f"X{i + 1}. {kind.replace('_', ' ').title()}"
        others = [c for c in "BCDEFGH" if c != col]
        assert all(ws[f"{c}{r}"].value is None for c in others), r

    # ---- Activities: PLAN row r, ACTUAL row r + 1 ----
    for k, act in enumerate(acts):
        r = first_act + 2 * k
        assert ws[f"H{r}"].value == f"{act['code']} {act['title']}"
        assert ws[f"I{r}"].value == float(act["annual_target"])
        assert (ws[f"J{r}"].value or "") == act["unit"]
        if act.get("unit_cost") not in (None, ""):
            assert ws[f"K{r}"].value == pytest.approx(float(act["unit_cost"]))
        assert ws[f"L{r}"].value == pytest.approx(float(act["total_cost"]))
        assert ws[f"M{r}"].value == f"=L{r}/$L${t}"
        assert (ws[f"N{r}"].value, ws[f"N{r + 1}"].value) == ("PLAN", "ACTUAL")
        assert [ws[f"{c}{r}"].value or 0 for c in MONTHS] == [float(v) for v in act["targets"]]
        actual = w["data"]["activities"][k]["actual"]
        assert [ws[f"{c}{r + 1}"].value for c in MONTHS] == [float(v) for v in actual]
        for c in "HIJKLM":
            assert ws[f"{c}{r + 1}"].value is None, (c, r + 1)  # the ACTUAL row carries no plan fields
        for i, c in enumerate(WEIGHTED):
            assert ws[f"{c}{r}"].value == f"={MONTHS[i]}{r}*$M{r}/$I{r}"
            assert ws[f"{c}{r + 1}"].value == f"={MONTHS[i]}{r + 1}*$M{r}/$I{r}"

    # ---- First activity, spelled out ----
    r = first_act
    assert ws[f"M{r}"].value == f"=L{r}/$L${t}"
    assert ws[f"AD{r}"].value == f"=O{r}*$M{r}/$I{r}" and ws[f"AO{r}"].value == f"=Z{r}*$M{r}/$I{r}"
    assert ws[f"AD{r + 1}"].value == f"=O{r + 1}*$M{r}/$I{r}"

    # ---- Total rows ----
    last = t - 1
    assert ws[f"B{t}"].value == ws[f"H{t}"].value == "TOTAL COST"
    assert ws[f"L{t}"].value == f"=SUM(L8:L{last})" and ws[f"M{t}"].value == f"=SUM(M8:M{last})"
    labels = {(t + 1, "U"): "Plan", (t + 1, "W"): "Periodic", (t + 2, "W"): "Commulative(Plan)",
              (t + 3, "U"): "Actual", (t + 3, "W"): "Periodic", (t + 4, "W"): "Commulative(Actual)",
              (t + 5, "U"): "Variance", (t + 5, "W"): "Periodic", (t + 6, "W"): "Commulative(Variance)",
              (t + 8, "U"): "FUNDS TOTAL", (t + 9, "U"): "FUNDS USED", (t + 10, "U"): "FUNDS REMAINING",
              (t + 11, "U"): "STATUS"}  # fmt: skip
    for (row, col), text in labels.items():
        assert ws[f"{col}{row}"].value == text, (row, col)
    assert ws[f"AD{t + 1}"].value == f'=SUMIF($N$8:$N${last},"PLAN",AD$8:AD${last})'
    assert ws[f"AE{t + 1}"].value == f'=SUMIF($N$8:$N${last},"PLAN",AE$8:AE${last})'
    assert ws[f"AD{t + 2}"].value == f"=AD{t + 1}"
    assert ws[f"AE{t + 2}"].value == f"=AE{t + 1}+AD{t + 2}"
    assert ws[f"AO{t + 2}"].value == f"=AO{t + 1}+AN{t + 2}"
    assert ws[f"AD{t + 3}"].value == f'=SUMIF($N$8:$N${last},"ACTUAL",AD$8:AD${last})'
    assert ws[f"AE{t + 4}"].value == f"=AE{t + 3}+AD{t + 4}"
    assert ws[f"AD{t + 5}"].value == f"=AD{t + 3}-AD{t + 1}"
    assert ws[f"AD{t + 6}"].value == f"=AD{t + 4}-AD{t + 2}"
    assert ws[f"W{t + 8}"].value == f"=L{t}"
    assert ws[f"W{t + 9}"].value == f"=AO{t + 4}*W{t + 8}"  # December: the last cumulative actual
    assert ws[f"W{t + 10}"].value == f"=W{t + 8}-W{t + 9}"
    assert ws[f"W{t + 11}"].value in ("ADVANCED", "ON-TIME", "DELAYED")

    # ---- Indicator header ----
    h = t + 13
    assert (ws[f"H{h}"].value, ws[f"L{h}"].value, ws[f"N{h}"].value) == ("OUTPUT INDICATORS", "TOTAL", "WTD%")
    assert [ws[f"{c}{h}"].value for c in MONTHS] == FULL == [ws[f"{c}{h}"].value for c in WEIGHTED]

    # ---- Columns AA:AC stay empty; sheet setup ----
    assert all(ws[f"{c}{row}"].value is None for c in ("AA", "AB", "AC") for row in range(1, ws.max_row + 1))
    assert ws.freeze_panes == "O8"
    assert ws.page_setup.orientation == "landscape" and int(ws.page_setup.paperSize) == 8
    # Fit to one page wide (fitToWidth 1 is the file format's default, so it is not written).
    assert ws.sheet_properties.pageSetUpPr.fitToPage and int(ws.page_setup.fitToHeight) == 0
    assert ws.page_setup.fitToWidth in (None, 1)
    assert ws[f"L{first_act}"].number_format == "#,##0.00" and ws[f"M{first_act}"].number_format == "0.00%"
    assert ws[f"AD{first_act}"].number_format == "0.00%"

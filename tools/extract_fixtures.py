#!/usr/bin/env python3
"""Extract MOST December-2023 test vectors from the reference workbook (MASTERPLAN 8.2, P4.2).

    backend/.venv/bin/python tools/extract_fixtures.py "reference/MOST MONITORING TOOL 2024.xlsx"

Writes backend/fixtures/most_fy2023_<sheet>.json for PME, HRM, RDI, AST, ILD (and GAS, see below).
Reads the activity rows only (typed values; a formula inside a data cell — e.g. a total cost —
uses Excel's saved result, D31). Weighted blocks and total rows are ignored and recomputed by the
engine. Never edits the workbook (reference/ is read-only).

Layout (8.2): an activity is a PLAN row followed by its ACTUAL row (label in column N);
title in H (F for PME and HRM), I = QTY, J = UNIT, K = UNIT COST, L = TOTAL COST, O:Z = Jan–Dec.

GAS is a money-measure office with a different layout (a working financial plan): row 311
"GRAND TOTAL PLAN" holds the year's plan (K311 = total, L:W = monthly plan amounts) and row 312
"ACTUAL MONTHLY DISBURSMENT" the amounts disbursed per month (mostly formulas; Excel's saved
results are used). It becomes one money-measure line: disbursed / planned (8.2: 80.16%).
Confirmed against the workbook on 2026-11-15.
"""

import json
import sys
from decimal import Decimal
from pathlib import Path

SHEETS = {
    "PME": {"title_col": "F"},
    "HRM": {"title_col": "F"},
    "RDI": {"title_col": "H"},
    "AST": {"title_col": "H"},
    "ILD": {"title_col": "H"},
}
GAS_LAYOUT = {
    "plan_row": 311,
    "disbursement_row": 312,
    "budget_cell": "K311",
    "month_cols": list("LMNOPQRSTUVW"),
}
MONTH_COLS = list("OPQRSTUVWXYZ")
OUT_DIR = Path(__file__).resolve().parent.parent / "backend" / "fixtures"


_CACHED = {}  # sheet title -> worksheet of cached (computed) values


def typed(cell):
    """A data cell's value. Typed values are used as they are. A formula in a data cell (e.g. a
    total cost written as =K20*14) is part of the plan, so Excel's saved result is used (D31).
    Weighted blocks and total rows are never read: the engine recomputes them."""
    value = cell.value
    if isinstance(value, str) and value.startswith("="):
        cached = _CACHED.get(cell.parent.title)
        return cached[cell.coordinate].value if cached is not None else None
    return value


def number(value, places: int | None = None) -> str:
    if value is None or value == "":
        return "0"
    if isinstance(value, str):
        value = value.replace(",", "").strip() or "0"
    d = Decimal(str(value))
    if places is not None:
        d = d.quantize(Decimal(1).scaleb(-places))
    return format(d, "f")


def extract_gas(ws) -> dict:
    """GAS: one money-measure line from the plan and disbursement rows (see module docstring)."""
    lay = GAS_LAYOUT
    budget = number(typed(ws[lay["budget_cell"]]), 2)
    plan_row, act_row = lay["plan_row"], lay["disbursement_row"]
    if (
        "PLAN" not in str(ws[f"H{plan_row}"].value or "").upper()
        or "DISBURS" not in str(ws[f"H{act_row}"].value or "").upper()
    ):
        raise ValueError("GAS: plan/disbursement rows are not where GAS_LAYOUT says; check the workbook")
    planned = [Decimal(number(typed(ws[f"{c}{plan_row}"]), 4)) for c in lay["month_cols"]]
    # Rounding the monthly plan to 4 decimals leaves a residue of a few ten-thousandths against the
    # budget (Excel's own sum is 107678521.99999993); it goes into the last planned month so the
    # months add up to the target exactly (D31).
    last = max(i for i, v in enumerate(planned) if v)
    planned[last] += Decimal(budget) - sum(planned)
    return {
        "sheet": ws.title,
        "measure_type": "money",
        "fiscal_year": "2023",
        "activities": [
            {
                "row": plan_row,
                "title": "General Administrative Support Services — financial plan (amounts disbursed)",
                "annual_target": budget,
                "unit": "PHP",
                "unit_cost": "",
                "total_cost": budget,
                "planned": [format(v, "f") for v in planned],
                "actual": [number(typed(ws[f"{c}{act_row}"]), 4) for c in lay["month_cols"]],
            }
        ],
    }


def extract_sheet(ws, title_col: str) -> dict:
    activities = []
    rows = list(range(1, ws.max_row + 1))
    for r in rows:
        label = typed(ws[f"N{r}"])
        if not (isinstance(label, str) and label.strip().upper() == "PLAN"):
            continue
        actual_label = typed(ws[f"N{r + 1}"])
        if not (isinstance(actual_label, str) and actual_label.strip().upper() == "ACTUAL"):
            raise ValueError(f"{ws.title}!N{r}: PLAN row not followed by an ACTUAL row")
        activities.append(
            {
                "row": r,
                "title": str(typed(ws[f"{title_col}{r}"]) or "").strip(),
                "annual_target": number(typed(ws[f"I{r}"])),
                "unit": str(typed(ws[f"J{r}"]) or "").strip(),
                "unit_cost": number(typed(ws[f"K{r}"])),
                "total_cost": number(typed(ws[f"L{r}"])),
                "planned": [number(typed(ws[f"{c}{r}"])) for c in MONTH_COLS],
                "actual": [number(typed(ws[f"{c}{r + 1}"])) for c in MONTH_COLS],
            }
        )
    if not activities:
        raise ValueError(f"{ws.title}: no PLAN/ACTUAL pairs found")
    return {"sheet": ws.title, "measure_type": "quantity", "fiscal_year": "2023", "activities": activities}


def main(path: str) -> None:
    import openpyxl

    wb = openpyxl.load_workbook(path, data_only=False, read_only=False)
    values = openpyxl.load_workbook(path, data_only=True, read_only=False)
    for sheet in list(SHEETS) + ["GAS"]:
        _CACHED[sheet] = values[sheet]
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    for sheet, spec in SHEETS.items():
        data = extract_sheet(wb[sheet], spec["title_col"])
        out = OUT_DIR / f"most_fy2023_{sheet.lower()}.json"
        out.write_text(json.dumps(data, indent=1) + "\n")
        print(f"{sheet}: {len(data['activities'])} activities -> {out.name}")
    gas = extract_gas(wb["GAS"])
    out = OUT_DIR / "most_fy2023_gas.json"
    out.write_text(json.dumps(gas, indent=1) + "\n")
    print(f"GAS: 1 money-measure line, budget {gas['activities'][0]['total_cost']} -> {out.name}")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        sys.exit(__doc__)
    main(sys.argv[1])

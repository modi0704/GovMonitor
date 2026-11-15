#!/usr/bin/env python3
"""Extract MOST December-2023 test vectors from the reference workbook (MASTERPLAN 8.2, P4.2).

    backend/.venv/bin/python tools/extract_fixtures.py "reference/MOST MONITORING TOOL 2024.xlsx"

Writes backend/fixtures/most_fy2023_<sheet>.json for PME, HRM, RDI, AST, ILD (and GAS, see below).
Reads typed values only: formulas are ignored and every weighted block / total row is recomputed by
the engine. Never edits the workbook (reference/ is read-only).

Layout (8.2): an activity is a PLAN row followed by its ACTUAL row (label in column N);
title in H (F for PME and HRM), I = QTY, J = UNIT, K = UNIT COST, L = TOTAL COST, O:Z = Jan–Dec.

GAS is a money-measure office with a different layout ("plan cost and disbursement rows"); its
exact rows must be confirmed against the file before extraction, so this script refuses GAS until
GAS_LAYOUT below is filled in from the real workbook. Do not invent data.
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
GAS_LAYOUT: dict | None = None  # e.g. {"plan_row": ..., "disbursement_row": ..., "budget_cell": "K311"}
MONTH_COLS = list("OPQRSTUVWXYZ")
OUT_DIR = Path(__file__).resolve().parent.parent / "backend" / "fixtures"


def typed(cell):
    """A cell's typed value; formulas (strings starting with '=') count as empty."""
    value = cell.value
    if isinstance(value, str) and value.startswith("="):
        return None
    return value


def number(value) -> str:
    if value is None or value == "":
        return "0"
    if isinstance(value, str):
        value = value.replace(",", "").strip() or "0"
    return str(Decimal(str(value)))


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
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    for sheet, spec in SHEETS.items():
        data = extract_sheet(wb[sheet], spec["title_col"])
        out = OUT_DIR / f"most_fy2023_{sheet.lower()}.json"
        out.write_text(json.dumps(data, indent=1) + "\n")
        print(f"{sheet}: {len(data['activities'])} activities -> {out.name}")
    if GAS_LAYOUT is None:
        print("GAS: skipped — confirm its plan/disbursement rows in the workbook and fill GAS_LAYOUT")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        sys.exit(__doc__)
    main(sys.argv[1])

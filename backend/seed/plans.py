"""Demo plans (sample data only). The 8.1 worked example stands in for the MOST fixtures while
P4.2 is blocked; when backend/fixtures/most_fy2023_*.json exist they are loaded instead."""

import json
from pathlib import Path

FIXTURES = Path(__file__).resolve().parent.parent / "fixtures"


def months(values):
    vals = [str(v) for v in values]
    return vals + ["0"] * (12 - len(vals))


WORKED_EXAMPLE = {
    "office": "PME",
    "output": "Planning, monitoring and evaluation services provided",
    "activities": [
        ("A", "Conduct monitoring visits to provincial centers", "visit", "10", "60000", "600000", [2, 3, 5]),
        ("B", "Prepare quarterly performance reports", "report", "4", "75000", "300000", [0, 2, 2]),
        ("C", "Hold the annual planning workshop", "workshop", "1", "100000", "100000", [0, 0, 1]),
    ],
}


def worked_example_rows():
    rows = [
        {
            "client_key": "out",
            "row_kind": "output",
            "code": "O1",
            "title": WORKED_EXAMPLE["output"],
            "sort_order": 0,
        }
    ]
    for i, (code, title, unit, target, unit_cost, cost, plan) in enumerate(
        WORKED_EXAMPLE["activities"], start=1
    ):
        rows.append(
            {
                "client_key": code,
                "parent": "out",
                "row_kind": "activity",
                "code": code,
                "title": title,
                "sort_order": i * 10,
                "measure_type": "quantity",
                "unit": unit,
                "annual_target": target,
                "unit_cost": unit_cost,
                "total_cost": cost,
                "targets": months(plan),
            }
        )
    return rows


def fixture_plans() -> dict[str, list]:
    """office code -> rows, from the MOST fixtures when they exist (P4.2)."""
    out = {}
    for path in sorted(FIXTURES.glob("most_fy2023_*.json")):
        data = json.loads(path.read_text())
        rows = []
        for i, a in enumerate(data["activities"], start=1):
            rows.append(
                {
                    "client_key": f"r{i}",
                    "row_kind": "activity",
                    "code": f"{data['sheet']}-{i}",
                    "title": a["title"] or f"Activity {i}",
                    "sort_order": i * 10,
                    "measure_type": data.get("measure_type", "quantity"),
                    "unit": a.get("unit", ""),
                    "annual_target": a["annual_target"],
                    "unit_cost": a.get("unit_cost") or None,
                    "total_cost": a["total_cost"],
                    "targets": a["planned"],
                }
            )
        out[data["sheet"]] = rows
    return out

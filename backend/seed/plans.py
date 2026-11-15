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


def fixture_actuals() -> dict[str, dict[str, list]]:
    """office code -> {row code: 12 monthly actuals}, from the MOST fixtures (same codes as fixture_plans)."""
    out = {}
    for path in sorted(FIXTURES.glob("most_fy2023_*.json")):
        data = json.loads(path.read_text())
        out[data["sheet"]] = {
            f"{data['sheet']}-{i}": a["actual"] for i, a in enumerate(data["activities"], start=1)
        }
    return out


# ---- Sample Bureau (P14.4): generic, generated plans for a differently shaped agency ------------

BUREAU_UNITS = ("R1-P1-D1-U1", "R1-P1-D1-U2", "R1-P1-D2-U1", "R2-P1-D1-U1")
BUREAU_ACTIVITIES = (
    # title, unit, target, monthly pattern, cost per unit, measure
    ("Community consultations", "session", 12, "even", 15000, "quantity"),
    ("Farmer field schools", "school", 6, "front", 120000, "quantity"),
    ("Monitoring visits", "visit", 1, "monthly", 2000, "recurring"),
    ("Technology demonstration plots", "plot", 4, "back", 80000, "quantity"),
)


def _spread(total: int, pattern: str) -> list[int]:
    if pattern == "monthly":
        return [1] * 12
    weights = {"even": [1] * 12, "front": [3] * 4 + [1] * 8, "back": [1] * 8 + [3] * 4}[pattern]
    raw = [total * w / sum(weights) for w in weights]
    out = [int(v) for v in raw]
    for i in sorted(range(12), key=lambda k: raw[k] - out[k], reverse=True)[: total - sum(out)]:
        out[i] += 1
    return out


def bureau_plan_rows(unit_code: str) -> list[dict]:
    """One output with four activities per unit; equal weighting ignores the costs on purpose."""
    rows = [{"client_key": "o", "row_kind": "output", "code": f"{unit_code}-O1",
             "title": "Rural services delivered", "sort_order": 0}]  # fmt: skip
    for i, (title, unit, target, pattern, unit_cost, measure) in enumerate(BUREAU_ACTIVITIES, start=1):
        rows.append(
            {
                "client_key": f"a{i}", "parent": "o", "row_kind": "activity", "code": f"{unit_code}-{i}",
                "title": title, "sort_order": i * 10, "measure_type": measure, "unit": unit,
                "annual_target": str(target), "unit_cost": str(unit_cost),
                "total_cost": str(unit_cost * target), "targets": [str(v) for v in _spread(target, pattern)],
            }
        )  # fmt: skip
    return rows


def bureau_actual(unit_index: int, activity_index: int, month: int, planned: int) -> str:
    """Deterministic accomplishments: most units close to plan, one over-delivering (so the 100%
    ceiling of the capped preset matters) and one behind."""
    if planned == 0:
        return "0"
    factor = {0: 1.0, 1: 1.5, 2: 0.5, 3: 1.0}[unit_index]
    if activity_index == 4 and month == 1:
        factor = 0  # a slow start somewhere
    return str(max(0, round(planned * factor)))

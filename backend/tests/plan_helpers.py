"""Helpers to build plans through the public API (used by tests and mirrored by the demo seed)."""

WORKED_EXAMPLE = [
    # code, title, cost, target, monthly plan (Jan..Mar)
    ("A", "Activity A", "600000", "10", ["2", "3", "5"]),
    ("B", "Activity B", "300000", "4", ["0", "2", "2"]),
    ("C", "Activity C", "100000", "1", ["0", "0", "1"]),
]


def months(values):
    return [str(v) for v in values] + ["0"] * (12 - len(values))


def worked_example_rows():
    rows = [{"client_key": "out", "row_kind": "output", "code": "O1", "title": "Output one", "sort_order": 0}]
    for i, (code, title, cost, target, plan) in enumerate(WORKED_EXAMPLE, start=1):
        rows.append(
            {
                "client_key": code,
                "parent": "out",
                "row_kind": "activity",
                "code": code,
                "title": title,
                "sort_order": i * 10,
                "measure_type": "quantity",
                "unit": "unit",
                "annual_target": target,
                "total_cost": cost,
                "targets": months(plan),
            }
        )
    return rows

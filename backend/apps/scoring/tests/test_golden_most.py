"""Golden tests against the MOST December-2023 figures (MASTERPLAN 8.2, P4.6).

They need backend/fixtures/most_fy2023_<sheet>.json from tools/extract_fixtures.py (P4.2), which
needs the reference workbook. Without the fixtures they are skipped, never faked.
"""

import json
from decimal import Decimal as D
from pathlib import Path

import pytest

from apps.scoring import engine
from apps.scoring.types import ActivityInput, Profile

FIXTURES = Path(__file__).resolve().parents[3] / "fixtures"
EXPECTED_DEC = {
    "PME": "0.9583",
    "HRM": "0.8368",
    "RDI": "0.9907",
    "AST": "0.5876",
    "ILD": "0.9023",
    "GAS": "0.8016",
}
BUDGETS = {"RDI": D(21_123_500), "AST": D(13_095_400), "ILD": D(21_571_200), "GAS": D(107_678_522)}
TOLERANCE = D("0.00005")  # ±0.005 percentage points


def load(sheet):
    path = FIXTURES / f"most_fy2023_{sheet.lower()}.json"
    if not path.exists():
        pytest.skip(f"{path.name} missing: reference workbook not available (P4.2 blocked)")
    data = json.loads(path.read_text())
    return [
        ActivityInput(
            id=str(a["row"]),
            measure_type=data["measure_type"],
            annual_target=D(a["annual_target"]),
            total_cost=D(a["total_cost"]),
            planned=tuple(D(v) for v in a["planned"]),
            actual=tuple(D(v) for v in a["actual"]),
            title=a["title"],
        )
        for a in data["activities"]
    ]


@pytest.mark.parametrize("sheet", sorted(EXPECTED_DEC))
def test_sheet_december_cumulative_accomplishment(sheet):
    activities = load(sheet)
    result = engine.plan_result(activities, [], Profile())
    assert abs(result.cum_actual[11] - D(EXPECTED_DEC[sheet])) <= TOLERANCE
    if sheet in BUDGETS:
        assert result.funds_total == BUDGETS[sheet]


def test_rds_rollup():
    parts = [engine.plan_result(load(s), [], Profile()) for s in ("RDI", "AST", "ILD")]
    assert abs(engine.rollup(parts, Profile()).cum_actual[11] - D("0.8619")) <= TOLERANCE


def test_provincial_ranking_vector():
    """December 2023 deck: provincial centers ranked 1–7 (values in percent)."""
    deck = [
        ("Basilan", "96.27"),
        ("Maguindanao", "96.23"),
        ("SGA", "96.18"),
        ("Lanao del Sur", "93.50"),
        ("Cotabato", "87.74"),
        ("Tawi-Tawi", "87.37"),
        ("Sulu", "76.57"),
    ]
    rows = engine.rank([(name, D(v) / 100) for name, v in reversed(deck)])
    assert [(r.office_id, r.rank) for r in rows] == [(name, i) for i, (name, _) in enumerate(deck, start=1)]

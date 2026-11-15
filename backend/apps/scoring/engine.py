"""Scoring engine (MASTERPLAN 7): pure functions over ``apps.scoring.types``.

No database access and no Django imports (enforced by tests/test_purity.py). Every score in the
product comes from here: results services, dashboards, exports and the plan editor preview.
"""

from apps.scoring.types import (  # noqa: F401 — the engine is implemented in P4.3/P4.4
    ActivityInput,
    IndicatorInput,
    OfficeResult,
    Profile,
    RankingRow,
)

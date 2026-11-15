"""P4.1: the engine is pure — no ORM, no Django, no I/O libraries."""

import ast
import pathlib

import pytest

SCORING = pathlib.Path(__file__).resolve().parent.parent
PURE_MODULES = ["engine.py", "types.py", "presets.py"]
ALLOWED_TOP_LEVEL = {
    "decimal",
    "dataclasses",
    "typing",
    "itertools",
    "math",
    "collections",
    "functools",
    "apps",
}


def imported_modules(path: pathlib.Path) -> set[str]:
    tree = ast.parse(path.read_text())
    names = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            names.add(node.module)
    return names


@pytest.mark.parametrize("module", PURE_MODULES)
def test_scoring_modules_import_nothing_impure(module):
    path = SCORING / module
    if not path.exists():
        pytest.skip(f"{module} not written yet")
    for name in imported_modules(path):
        top = name.split(".")[0]
        assert top in ALLOWED_TOP_LEVEL, f"{module} imports {name}"
        if top == "apps":
            assert name.startswith("apps.scoring"), f"{module} imports {name} (only apps.scoring.* allowed)"


def test_types_are_frozen_dataclasses():
    from dataclasses import fields, is_dataclass

    from apps.scoring import types

    for cls in (
        types.Profile,
        types.ActivityInput,
        types.IndicatorInput,
        types.OfficeResult,
        types.RankingRow,
    ):
        assert is_dataclass(cls) and cls.__dataclass_params__.frozen
        assert fields(cls)

"""P14.5: docs/API.md lists every API route (re-run tools/api_docs.py after changing routes)."""

from pathlib import Path

from django.urls import get_resolver

API_MD = Path(__file__).resolve().parents[2] / "docs" / "API.md"


def test_every_route_is_documented():
    def walk(patterns, prefix=""):
        for p in patterns:
            if hasattr(p, "url_patterns"):
                yield from walk(p.url_patterns, prefix + str(p.pattern))
            elif (prefix + str(p.pattern)).startswith(("api/v1/", "platform/api/")):
                yield p.name

    text = API_MD.read_text()
    missing = sorted({name for name in walk(get_resolver().url_patterns) if f"`{name}`" not in text})
    assert not missing, f"run tools/api_docs.py: undocumented routes {missing}"
    assert "|  |" not in text, "an operation has no description (add a docstring or tools/api_summaries.json)"

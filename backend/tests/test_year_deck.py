"""The year's over-all performance deck (agency year-end presentation) on the sample ministry."""

import io
import os
from pathlib import Path

import pytest
from pptx import Presentation

from apps.exports import pptx_year
from apps.exports import scope as export_scope
from apps.tenancy import context
from tests.test_deck import HAS_MOST, most  # noqa: F401 — shared fixture


def build(agency_id, office, period_id, title=""):
    with context.agency_context(agency_id):
        sc = export_scope.resolve(
            {"scope": "agency", "office_id": str(office.id), "period_id": str(period_id), "view": "owner"}
        )
        return pptx_year.build(sc, title=title)


def texts(slide) -> str:
    return " ".join(s.text_frame.text for s in slide.shapes if s.has_text_frame)


@pytest.mark.skipif(not HAS_MOST, reason="P4.2 fixtures missing")
@pytest.mark.django_db(databases=["default", "owner"], transaction=True)
def test_year_deck_follows_the_year_end_presentation(most, tmp_path):  # noqa: F811
    data, summary = build(
        most["agency"].id, most["root"], most["december"].id, "Ministry's over-all performance"
    )
    prs = Presentation(io.BytesIO(data))
    kinds = [k for k, _ in summary["map"]]
    assert kinds[0] == "title" and kinds[1] == "year_overall" and kinds[-1] == "closing"
    assert "MINISTRY'S OVER-ALL PERFORMANCE" in texts(prs.slides[0])
    assert "AS OF DECEMBER 31, 2023" in texts(prs.slides[0])
    for needed in ("year_group", "office", "year_activities", "ranking_activities"):
        assert needed in kinds, needed
    assert "ranking_indicators" not in kinds  # the sample ministry records no output indicators
    overall = prs.slides[1]
    names = {s.name for s in overall.shapes}
    assert {"chart-activities", "chart-indicators", "activities-plan", "indicators-achieved"} <= names
    # The over-all panel shows the same figures as the dashboard.
    api = most["api"]
    dash = api.get("/api/v1/dashboard", office=str(most["root"].id), period=str(most["december"].id)).json()
    head = dash["headline"]
    plan_tile = next(s for s in overall.shapes if s.name == "activities-plan").text_frame.text
    assert f"{float(head['cum_plan']) * 100:,.2f}%" in plan_tile
    # Activity grid: one row per activity of the office's plan, dark/yellow month cells.
    grid = next(i for i, k in enumerate(kinds) if k == "year_activities")
    table = next(s for s in prs.slides[grid].shapes if s.has_table).table
    assert [c.text for c in table.rows[0].cells][:3] == ["Activity", "Target", "JAN"]
    out = os.environ.get("YEAR_DECK_OUT")
    if out:
        Path(out).write_bytes(data)


@pytest.mark.skipif(not HAS_MOST, reason="P4.2 fixtures missing")
@pytest.mark.django_db(databases=["default", "owner"], transaction=True)
def test_year_deck_is_queued_through_the_api(most):  # noqa: F811
    api = most["api"]
    body = {"scope": "agency", "period_id": str(most["december"].id), "style": "year", "title": "Over-all"}
    r = api.post("/api/v1/exports/pptx", body)
    assert r.status_code == 202, r.content
    assert api.post("/api/v1/exports/pptx", {**body, "style": "other"}).status_code == 400
    assert api.post("/api/v1/exports/pptx", {**body, "title": "x" * 121}).status_code == 400


def test_indicator_ranking_shares_ranks_on_ties():
    from decimal import Decimal as D
    from types import SimpleNamespace as NS

    from apps.scoring import presets

    deck = pptx_year.YearDeck.__new__(pptx_year.YearDeck)
    deck.data = NS(profile=presets.profile_from_settings({}))
    offices = [NS(id=i, code=c, name=c) for i, c in enumerate("ABCD")]
    deck.year = pptx_year.YearData(
        indicator_series={"0": [D("0.9")], "1": [D("1")], "2": [D("0.9")], "3": [None]}
    )
    rows = deck.indicator_ranking_rows(offices)
    assert [(r[0], r[1]) for r in rows] == [(1, "B B"), (2, "A A"), (2, "C C"), ("—", "D D")]

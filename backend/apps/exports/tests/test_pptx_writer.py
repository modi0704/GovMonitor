"""P10.1: the PowerPoint deck (MASTERPLAN 10) on the 8.1 worked example."""

import io

import pytest
from pptx import Presentation

from apps.exports import pptx_writer
from apps.exports import scope as export_scope
from apps.exports.text_fit import fit, text_width
from apps.tenancy import context
from tests.export_helpers import worked_example_world

pytestmark = pytest.mark.django_db


def deck(w, scope="agency", office=None, month=3, **kw):
    office = office or w["root"]
    with context.agency_context(w["agency"].id):
        sc = export_scope.resolve(
            {
                "scope": scope,
                "office_id": str(office.id),
                "period_id": w["periods"][month]["id"],
                "view": "owner",
            }
        )
        data, summary = pptx_writer.build(sc, **kw)
    return Presentation(io.BytesIO(data)), summary


def shapes(slide):
    return {s.name: s for s in slide.shapes}


def test_deck_sequence_and_the_office_slide():
    w = worked_example_world()
    prs, summary = deck(w)
    kinds = [k for k, _ in summary["map"]]
    # ROOT (overall), DIV; OTHER and UNIT have no result; one children ranking set under ROOT.
    assert kinds == ["title", "overall", "office", "ranking", "notes"]
    assert prs.slide_width / prs.slide_height == pytest.approx(16 / 9, rel=0.01)

    title = prs.slides[0]
    texts = [s.text_frame.text for s in title.shapes if s.has_text_frame]
    assert w["agency"].name in texts and "As of March 2026" in texts
    assert "Performance Monitoring Report" in texts

    div = shapes(prs.slides[2])
    assert div["header-title"].text_frame.text == "DIV (ACCOMPLISHMENT REPORT)"
    assert div["header-label"].text_frame.text == "PROVISIONAL"
    assert div["tile-actual"].text_frame.text == "ACTUAL\n78.00%"
    assert div["tile-variance"].text_frame.text == "VARIANCE\n-22.00%"
    assert div["tile-status"].text_frame.text == "STATUS\nDELAYED"
    curve = div["chart-scurve"].chart.plots[0]
    plan, actual = (list(s.values) for s in curve.series)
    assert [round(v, 6) for v in plan[:3]] == [0.12, 0.45, 1.0]
    assert [round(v, 6) for v in actual[:3]] == [0.12, 0.315, 0.78] and actual[3:] == [None] * 9
    assert list(curve.categories)[:3] == ["JAN", "FEB", "MAR"]
    funds = div["chart-funds"].chart.plots[0]
    assert list(funds.series[0].values) == [780000.0, 220000.0]
    assert "chart-children" not in div  # DIV's only child (UNIT) has no result
    assert "chart-children" in shapes(prs.slides[1])  # ROOT shows DIV
    assert div["footer-page"].text_frame.text == "Page 3 of 5"


def test_slide_groups_can_be_left_out():
    w = worked_example_world()
    _, summary = deck(w, groups=("offices",))
    assert [k for k, _ in summary["map"]] == ["title", "office", "office", "notes"]


def test_text_is_cut_with_an_ellipsis_after_measuring():
    long = "Regional Office for Science and Technology Services of the Autonomous Region " * 2
    cut = fit(long, 200, 12)
    assert cut.endswith("…") and text_width(cut, 12) <= 200
    assert fit("Short name", 200, 12) == "Short name"
    assert text_width("WWW", 10) > text_width("iii", 10)

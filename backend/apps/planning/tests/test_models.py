import datetime

import pytest
from django.db import IntegrityError, transaction

from apps.planning import services
from apps.planning.models import FiscalYear, Plan
from apps.tenancy import context
from apps.tenancy.models import Agency
from tests.factories import make_agency, make_office, make_root

pytestmark = pytest.mark.django_db


@pytest.fixture
def ctx():
    agency = make_agency("alpha", timezone="Asia/Manila", fiscal_year_start_month=7)
    root = make_root(agency)
    with context.agency_context(agency.id):
        yield agency, make_office(root, "DIV")


def test_fiscal_year_creates_twelve_periods_from_the_agency_start_month(ctx):
    fy = services.create_fiscal_year("FY2026", 2026)
    periods = list(fy.periods.order_by("month_index"))
    assert (fy.start_date, fy.end_date) == (datetime.date(2026, 7, 1), datetime.date(2027, 6, 30))
    assert [p.start_date.month for p in periods] == [7, 8, 9, 10, 11, 12, 1, 2, 3, 4, 5, 6]
    assert periods[-1].end_date == datetime.date(2027, 6, 30)
    # Cutoff: day 10 of the following month, 23:59:59 Manila time (UTC+8).
    assert periods[0].cutoff_at == datetime.datetime(2026, 8, 10, 15, 59, 59, tzinfo=datetime.UTC)
    assert fy.profile.preset == "workbook_compatible" and fy.profile.version == 1
    assert fy.status == "draft"


def test_fiscal_year_labels_and_overlap(ctx):
    services.create_fiscal_year("FY2026", 2026)
    for label, year in (("fy2026", 2027), ("Overlap", 2026)):
        with pytest.raises(services.PlanningError):
            services.create_fiscal_year(label, year)
    services.create_fiscal_year("FY2027", 2027)
    assert FiscalYear.objects.count() == 2


def test_status_transitions(ctx):
    fy = services.create_fiscal_year("FY2026", 2026)
    with pytest.raises(services.PlanningError):
        services.set_fiscal_year_status(fy, "closed")
    services.set_fiscal_year_status(fy, "open")
    services.set_fiscal_year_status(fy, "closed")
    assert fy.status == "closed"


def test_one_approved_and_one_open_version_per_office_year(ctx):
    _, office = ctx
    fy = services.create_fiscal_year("FY2026", 2026)
    Plan.objects.create(office=office, fiscal_year=fy, version=1, status="approved")
    with pytest.raises(IntegrityError), transaction.atomic():
        Plan.objects.create(office=office, fiscal_year=fy, version=2, status="approved")
    Plan.objects.create(office=office, fiscal_year=fy, version=2, status="draft")
    with pytest.raises(IntegrityError), transaction.atomic():
        Plan.objects.create(office=office, fiscal_year=fy, version=3, status="submitted")


def test_profile_converts_to_engine_profile(ctx):
    fy = services.create_fiscal_year("FY2026", 2026)
    from apps.scoring.types import Profile

    assert fy.profile.to_engine() == Profile()
    assert Agency.objects.get().fiscal_year_start_month == 7

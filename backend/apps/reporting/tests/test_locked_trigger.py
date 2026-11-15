"""P7.5: the database refuses changes to accomplishments and files of a locked month."""

import pytest
from django.db import DatabaseError, connection, transaction

from apps.planning.models import ReportingPeriod
from apps.reporting.models import ActivityActual, Attachment, IndicatorActual
from apps.tenancy import context
from tests.isolation_seed import seed_two_agencies

pytestmark = pytest.mark.django_db(databases=["default", "owner"], transaction=True)


def test_trigger_blocks_insert_update_delete_in_locked_month():
    a, _ = seed_two_agencies()
    with context.agency_context(a["agency"].id):
        period = a["period"]
        actual = ActivityActual.objects.get(period=period)
        ReportingPeriod.objects.filter(pk=period.pk).update(status="locked")
        attempts = [
            lambda: ActivityActual.objects.filter(pk=actual.pk).update(actual_qty=99),
            lambda: ActivityActual.objects.filter(pk=actual.pk).delete(),
            lambda: IndicatorActual.objects.filter(period=period).update(actual_value=5),
            lambda: Attachment.objects.filter(period=period).update(description="changed"),
            lambda: ActivityActual.objects.create(
                activity_lineage_id=a["indicator"].lineage_id, period=period, office=a["child"], actual_qty=1
            ),
        ]
        for attempt in attempts:
            with pytest.raises(DatabaseError, match="period is locked"), transaction.atomic():
                attempt()
        # Moving a row out of a locked month is refused too.
        other = period.fiscal_year.periods.get(month_index=2)
        with pytest.raises(DatabaseError, match="period is locked"), transaction.atomic():
            ActivityActual.objects.filter(pk=actual.pk).update(period=other)
        # Open months are unaffected.
        ReportingPeriod.objects.filter(pk=period.pk).update(status="open")
        assert ActivityActual.objects.filter(pk=actual.pk).update(actual_qty=3) == 1
        with connection.cursor() as cur:
            cur.execute("SELECT count(*) FROM activity_actual WHERE actual_qty = 3")
            assert cur.fetchone()[0] == 1

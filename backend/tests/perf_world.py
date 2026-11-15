"""A synthetic agency at the D13 sizing ceiling: 500 offices, 5,000 activities, 12 months of
targets and six months of accomplishments. Built with bulk inserts (not through the API) so that
performance tests start quickly."""

import random
import uuid
from decimal import Decimal

from apps.planning.models import Activity, ActivityTarget, Plan
from apps.planning.services import create_fiscal_year, set_fiscal_year_status
from apps.reporting.models import ActivityActual
from apps.structure.models import Office, OfficeGroup, OfficeGroupMember, OrgLevel
from apps.tenancy import context
from tests.factories import assign, make_agency, make_root, make_user

SERVICES, DIVISIONS_PER_SERVICE, UNITS_PER_DIVISION = 10, 7, 6  # 10 + 70 + 420 + root = 501 offices
ACTIVITIES_PER_DIVISION = 70  # 70 divisions x 70 = 4,900 activities, plus 100 on the services


def build(code="perf"):
    rng = random.Random(7)
    agency = make_agency(code)
    root = make_root(agency)
    boss = make_user(agency, f"boss@{code}.gov")
    assign(boss, root, "admin")
    with context.agency_context(agency.id):
        levels = {d: OrgLevel.objects.get_or_create(depth=d, defaults={"name": f"L{d}"})[0] for d in range(4)}
        services, divisions, units = [], [], []
        for s in range(SERVICES):
            svc = Office(id=uuid.uuid4(), parent=root, level=levels[1], name=f"Service {s}", code=f"S{s}")
            svc.path = f"{root.path}{svc.id}/"
            services.append(svc)
            for d in range(DIVISIONS_PER_SERVICE):
                div = Office(
                    id=uuid.uuid4(), parent=svc, level=levels[2], name=f"Division {s}.{d}", code=f"D{s}-{d}"
                )
                div.path = f"{svc.path}{div.id}/"
                divisions.append(div)
                for u in range(UNITS_PER_DIVISION):
                    unit = Office(
                        id=uuid.uuid4(),
                        parent=div,
                        level=levels[3],
                        name=f"Unit {s}.{d}.{u}",
                        code=f"U{s}-{d}-{u}",
                    )
                    unit.path = f"{div.path}{unit.id}/"
                    units.append(unit)
        Office.objects.bulk_create(services + divisions + units)
        group = OfficeGroup.objects.create(name="Field units")
        OfficeGroupMember.objects.bulk_create([OfficeGroupMember(group=group, office=u) for u in units[:60]])

        fy = create_fiscal_year("PERF", 2026)
        set_fiscal_year_status(fy, "open")
        periods = {p.month_index: p for p in fy.periods.all()}
        owners = [(div, ACTIVITIES_PER_DIVISION) for div in divisions] + [(svc, 10) for svc in services]
        plans = [Plan(office=o, fiscal_year=fy, status="approved", version=1) for o, _ in owners]
        Plan.objects.bulk_create(plans)
        activities, targets, actuals = [], [], []
        for plan, (office, n) in zip(plans, owners, strict=True):
            for i in range(n):
                target = Decimal(rng.randint(1, 24))
                act = Activity(
                    plan=plan,
                    lineage_id=uuid.uuid4(),
                    row_kind="activity",
                    code=f"{office.code}-{i}",
                    title=f"Activity {i}",
                    sort_order=i,
                    measure_type="quantity",
                    annual_target=target,
                    total_cost=Decimal(rng.randint(1000, 900000)),
                    implementing_office=rng.choice(units) if rng.random() < 0.3 else office,
                )
                activities.append(act)
                per_month = target / 12
                for m in range(1, 13):
                    targets.append(
                        ActivityTarget(
                            activity=act, period=periods[m], planned_qty=per_month.quantize(Decimal("0.0001"))
                        )
                    )
                for m in range(1, 7):
                    actuals.append(
                        ActivityActual(
                            activity_lineage_id=act.lineage_id,
                            period=periods[m],
                            office=office,
                            actual_qty=Decimal(rng.randint(0, 3)),
                        )
                    )
        Activity.objects.bulk_create(activities, batch_size=2000)
        ActivityTarget.objects.bulk_create(targets, batch_size=5000)
        ActivityActual.objects.bulk_create(actuals, batch_size=5000)
    return {
        "agency": agency,
        "root": root,
        "fy": fy,
        "periods": periods,
        "boss": boss,
        "activities": len(activities),
        "offices": 1 + len(services) + len(divisions) + len(units),
    }

"""Tenant isolation (MASTERPLAN 6.1, P1.9).

(a) with agency A set, raw SQL on every tenant table returns no rows of agency B;
(b) writing a row carrying another agency's id fails;
(c) with no agency set, every tenant table returns zero rows;
(d) every model with an ``agency_id`` has a forced RLS policy, and every model without one is on an
    explicit allow-list.
"""

import pytest
from django.apps import apps
from django.db import DatabaseError, IntegrityError, connection, connections, transaction

from apps.tenancy import context
from tests.isolation_seed import BUILDERS, seed_two_agencies

# Models that legitimately have no agency_id (6.1: platform_admin and Django internals).
NO_AGENCY_ALLOWLIST = {
    "tenancy.platformadmin",
    "contenttypes.contenttype",
    "auth.permission",
    "auth.group",
    "auth.group_permissions",
    "auth.permission_group",
    "sessions.session",
}
# Tables whose tenant column is not called agency_id.
TENANT_COLUMN = {"agency": "id"}


def _tenant_tables():
    tables = {}
    for model in apps.get_models(include_auto_created=True):
        table = model._meta.db_table
        if table in TENANT_COLUMN:
            tables[table] = TENANT_COLUMN[table]
        elif any(f.column == "agency_id" for f in model._meta.concrete_fields):
            tables[table] = "agency_id"
    return tables


TENANT_TABLES = _tenant_tables()
DBS = ["default", "owner"]


def _q(name):
    return connection.ops.quote_name(name)


@pytest.mark.django_db(databases=DBS)
def test_meta_every_model_is_isolated_or_allow_listed():
    with connections["owner"].cursor() as cur:
        cur.execute(
            "SELECT c.relname, c.relrowsecurity, c.relforcerowsecurity, "
            "  EXISTS (SELECT 1 FROM pg_policies p "
            "          WHERE p.tablename = c.relname AND p.policyname = 'tenant_isolation') "
            "FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace "
            "WHERE n.nspname = 'public' AND c.relkind = 'r'"
        )
        catalog = {name: (rls, forced, policy) for name, rls, forced, policy in cur.fetchall()}
    missing_policy, not_allowed = [], []
    for model in apps.get_models(include_auto_created=True):
        table = model._meta.db_table
        label = f"{model._meta.app_label}.{model._meta.model_name}"
        if table in TENANT_TABLES:
            if catalog.get(table) != (True, True, True):
                missing_policy.append(table)
        elif label not in NO_AGENCY_ALLOWLIST:
            not_allowed.append(label)
    assert not missing_policy, f"tenant tables without forced RLS + tenant_isolation policy: {missing_policy}"
    assert not not_allowed, f"models without agency_id that are not allow-listed: {not_allowed}"


def test_meta_every_tenant_table_has_an_isolation_seed_builder():
    assert set(TENANT_TABLES) <= set(BUILDERS), (
        f"add builders to tests/isolation_seed.py for: {sorted(set(TENANT_TABLES) - set(BUILDERS))}"
    )


@pytest.fixture
def two_agencies(django_db_blocker):
    a, b = seed_two_agencies()
    # Every tenant table really has rows for both agencies, otherwise the tests below prove nothing.
    with connections["owner"].cursor() as cur:
        for table, col in TENANT_TABLES.items():
            for objs in (a, b):
                cur.execute(f"SELECT count(*) FROM {_q(table)} WHERE {_q(col)} = %s", [objs["agency"].id])
                assert cur.fetchone()[0] > 0, f"no seed rows in {table} for {objs['agency'].code}"
    return a, b


@pytest.mark.django_db(databases=DBS, transaction=True)
def test_a_agency_a_cannot_read_agency_b(two_agencies):
    a, b = two_agencies
    with context.agency_context(a["agency"].id), connection.cursor() as cur:
        for table, col in TENANT_TABLES.items():
            cur.execute(f"SELECT count(*) FROM {_q(table)} WHERE {_q(col)} = %s", [b["agency"].id])
            assert cur.fetchone()[0] == 0, f"{table}: agency A sees agency B rows"
            cur.execute(f"SELECT count(*) FROM {_q(table)} WHERE {_q(col)} <> %s", [a["agency"].id])
            assert cur.fetchone()[0] == 0, f"{table}: agency A sees foreign rows"
            cur.execute(f"SELECT count(*) FROM {_q(table)}")
            assert cur.fetchone()[0] > 0, f"{table}: agency A cannot see its own rows"


def _columns(table):
    with connections["owner"].cursor() as cur:
        cur.execute(
            "SELECT column_name, data_type, column_default FROM information_schema.columns "
            "WHERE table_schema = 'public' AND table_name = %s ORDER BY ordinal_position",
            [table],
        )
        return cur.fetchall()


@pytest.mark.django_db(databases=DBS, transaction=True)
def test_b_writing_another_agencys_id_fails(two_agencies):
    a, b = two_agencies
    foreign = str(b["agency"].id)
    for table, col in TENANT_TABLES.items():
        cols, exprs = [], []
        for name, data_type, default in _columns(table):
            if name == col:
                cols.append(name)
                exprs.append("%s::uuid")
            elif name == "id" and data_type == "uuid":
                cols.append(name)
                exprs.append("gen_random_uuid()")
            elif name == "id" and default:
                continue  # serial key: let the default fill it
            elif name in ("email", "code"):
                cols.append(name)
                exprs.append(f"{_q(name)} || '-copy'")
            else:
                cols.append(name)
                exprs.append(_q(name))
        sql = (
            f"INSERT INTO {_q(table)} ({', '.join(_q(c) for c in cols)}) "
            f"SELECT {', '.join(exprs)} FROM {_q(table)} LIMIT 1"
        )
        with context.agency_context(a["agency"].id):
            # (b1) INSERT of a row with agency B's id while agency A is set
            with (
                pytest.raises(DatabaseError, match="row-level security"),
                transaction.atomic(),
                connection.cursor() as cur,
            ):
                cur.execute(sql, [foreign])
            # (b2) moving an own row to agency B (append-only tables refuse any UPDATE outright)
            with (
                pytest.raises(DatabaseError, match="row-level security|permission denied"),
                transaction.atomic(),
                connection.cursor() as cur,
            ):
                cur.execute(f"UPDATE {_q(table)} SET {_q(col)} = %s::uuid", [foreign])


@pytest.mark.django_db(databases=DBS, transaction=True)
def test_c_no_agency_sees_nothing(two_agencies):
    # System-wide rows (agency_id NULL, e.g. the default export templates) are readable by design;
    # no row that belongs to an agency may be.
    with transaction.atomic(), connection.cursor() as cur:
        context.set_agency(None)
        for table, col in TENANT_TABLES.items():
            cur.execute(f"SELECT count(*) FROM {_q(table)} WHERE {_q(col)} IS NOT NULL")
            assert cur.fetchone()[0] == 0, f"{table} visible with no agency set"
    # Also on a fresh connection where app.agency_id was never set (NULL, not '').
    connection.close()
    with connection.cursor() as cur:
        for table, col in TENANT_TABLES.items():
            cur.execute(f"SELECT count(*) FROM {_q(table)} WHERE {_q(col)} IS NOT NULL")
            assert cur.fetchone()[0] == 0, f"{table} visible on a fresh connection"


@pytest.mark.django_db(databases=DBS, transaction=True)
def test_system_rows_are_readable_but_not_writable(two_agencies):
    """export_template rows with no agency: every agency reads them, none can change them."""
    a, _ = two_agencies
    with connections["owner"].cursor() as cur:
        cur.execute(
            "INSERT INTO export_template (id, agency_id, kind, name, settings, is_default, updated_at) "
            "VALUES (gen_random_uuid(), NULL, 'pptx', 'System', '{}'::jsonb, false, now())"
        )
    with context.agency_context(a["agency"].id), connection.cursor() as cur:
        cur.execute("SELECT count(*) FROM export_template WHERE agency_id IS NULL")
        assert cur.fetchone()[0] >= 1
        cur.execute("UPDATE export_template SET name = 'mine' WHERE agency_id IS NULL")
        assert cur.rowcount == 0
        cur.execute("DELETE FROM export_template WHERE agency_id IS NULL")
        assert cur.rowcount == 0
        with pytest.raises(DatabaseError, match="row-level security"), transaction.atomic():
            cur.execute(
                "INSERT INTO export_template (id, agency_id, kind, name, settings, is_default, updated_at) "
                "VALUES (gen_random_uuid(), NULL, 'pptx', 'Mine', '{}'::jsonb, false, now())"
            )


@pytest.mark.django_db(databases=DBS, transaction=True)
def test_api_returns_404_for_other_agencys_ids(two_agencies):
    from django.test import Client

    from apps.tenancy.models import SupportGrant

    a, b = two_agencies
    b_grant = SupportGrant.objects.using("owner").get(agency_id=b["agency"].id)
    client = Client()
    r = client.post(
        "/api/v1/auth/login",
        {"email": a["user"].email, "password": "correct-horse-battery-staple"},
        content_type="application/json",
    )
    assert r.status_code == 200
    assert client.delete(f"/api/v1/support-grants/{b_grant.id}").status_code == 404
    assert [g["id"] for g in client.get("/api/v1/support-grants").json()] != [str(b_grant.id)]
    assert client.get("/api/v1/me").json()["agency"]["id"] == str(a["agency"].id)


@pytest.mark.django_db(databases=DBS)
def test_every_foreign_key_between_tenant_tables_is_tied_to_the_same_agency():
    """P14.1: foreign-key checks bypass RLS, so each tenant-to-tenant key is a composite
    (agency_id, id) constraint as well (apps/tenancy/db.py, added after every migrate)."""
    from apps.tenancy.db import _short, tenant_foreign_keys

    with connections["owner"].cursor() as cur:
        cur.execute("SELECT conname FROM pg_constraint WHERE contype = 'f'")
        names = {r[0] for r in cur.fetchall()}
    fks = tenant_foreign_keys()
    assert len(fks) > 30
    missing = [fk for fk in fks if _short(f"{fk[0]}_{fk[1]}_same_agency") not in names]
    assert not missing, f"tenant foreign keys without a same-agency constraint: {missing}"


@pytest.mark.django_db(databases=DBS, transaction=True)
def test_the_database_refuses_a_row_pointing_at_another_agency(two_agencies):
    """Even the owner role (no RLS) cannot file agency A's plan under agency B's office."""
    a, b = two_agencies
    with connections["owner"].cursor() as cur:
        cur.execute("SELECT id FROM fiscal_year WHERE agency_id = %s LIMIT 1", [a["agency"].id])
        (fy_a,) = cur.fetchone()
    with (
        pytest.raises(IntegrityError),
        transaction.atomic(using="owner"),
        connections["owner"].cursor() as cur,
    ):
        cur.execute("SET CONSTRAINTS ALL IMMEDIATE")
        cur.execute(
            "INSERT INTO plan (id, agency_id, office_id, fiscal_year_id, version, status, notes, created_at, "
            "updated_at) VALUES (gen_random_uuid(), %s, %s, %s, 99, 'draft', '', now(), now())",
            [a["agency"].id, b["child"].id, fy_a],
        )

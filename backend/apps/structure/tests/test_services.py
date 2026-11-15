import pytest

from apps.structure import services as svc
from apps.structure.models import Office, OfficeGroup, OrgLevel
from apps.tenancy import context
from tests.factories import make_agency

pytestmark = pytest.mark.django_db


@pytest.fixture
def agency_ctx():
    agency = make_agency("alpha")
    with context.agency_context(agency.id):
        yield agency


def build(spec, parent=None):
    """spec: {code: {child_code: {...}}} -> dict code->office"""
    out = {}
    for code, children in spec.items():
        office = svc.create_root(code, code) if parent is None else svc.create_office(parent, code, code)
        out[code] = office
        out.update(build(children, office))
    return out


def test_one_root_and_unique_codes(agency_ctx):
    root = svc.create_root("Ministry", "MIN")
    with pytest.raises(svc.StructureError) as e:
        svc.create_root("Another", "X")
    assert e.value.code == "root_exists"
    svc.create_office(root, "Division", "DIV")
    with pytest.raises(svc.StructureError) as e:
        svc.create_office(root, "Other", "div")  # case-insensitive
    assert e.value.code == "duplicate_code"


def test_five_level_tree_any_depth(agency_ctx):
    o = build({"L0": {"L1": {"L2": {"L3": {"L4": {}}}}}})
    assert [o[c].depth for c in ("L0", "L1", "L2", "L3", "L4")] == [0, 1, 2, 3, 4]
    assert [o[c].level.depth for c in ("L0", "L1", "L2", "L3", "L4")] == [0, 1, 2, 3, 4]
    assert OrgLevel.objects.count() == 5


def test_move_subtree_rewrites_paths_and_levels(agency_ctx):
    o = build({"R": {"A": {"A1": {"A1x": {}}}, "B": {}}})
    moved = svc.move_office(o["A1"], o["B"])
    a1, a1x = Office.objects.get(code="A1"), Office.objects.get(code="A1x")
    assert moved.parent_id == o["B"].pk
    assert a1.path == f"{o['B'].path}{a1.pk}/"
    assert a1x.path == f"{a1.path}{a1x.pk}/"
    assert (a1.depth, a1x.depth) == (2, 3) and (a1.level.depth, a1x.level.depth) == (2, 3)
    # every office's path is consistent with its parent chain
    for office in Office.objects.all():
        expected = f"/{office.pk}/" if office.parent_id is None else f"{office.parent.path}{office.pk}/"
        assert office.path == expected
    # moving one level up shifts levels back
    svc.move_office(o["A1"], o["R"])
    assert Office.objects.get(code="A1x").level.depth == 2


def test_no_cycles_and_root_is_fixed(agency_ctx):
    o = build({"R": {"A": {"A1": {}}}})
    for target in ("A", "A1"):
        with pytest.raises(svc.StructureError) as e:
            svc.move_office(o["A"], o[target])
        assert e.value.code == "cycle"
    with pytest.raises(svc.StructureError):
        svc.move_office(o["R"], o["A"])


def test_reorder(agency_ctx):
    o = build({"R": {"A": {}, "B": {}, "C": {}}})
    svc.reorder_children(o["R"], [o["C"].pk, o["A"].pk, o["B"].pk])
    assert list(
        Office.objects.filter(parent=o["R"]).order_by("sort_order").values_list("code", flat=True)
    ) == [
        "C",
        "A",
        "B",
    ]
    with pytest.raises(svc.StructureError):
        svc.reorder_children(o["R"], [o["A"].pk])


def test_deactivate_cascades_and_delete_rules(agency_ctx):
    o = build({"R": {"A": {"A1": {}}, "B": {}}})
    svc.set_active(o["A"], False)
    assert not Office.objects.get(code="A1").is_active
    with pytest.raises(svc.StructureError):
        svc.set_active(Office.objects.get(code="A1"), True)  # parent still inactive
    svc.set_active(o["A"], True)
    with pytest.raises(svc.StructureError) as e:
        svc.delete_office(o["A"])
    assert e.value.code == "has_children"
    with pytest.raises(svc.StructureError):
        svc.delete_office(o["R"])
    svc.delete_office(o["B"])
    assert not Office.objects.filter(code="B").exists()


def test_levels_and_groups(agency_ctx):
    o = build({"R": {"A": {}, "B": {}}})
    svc.set_level_names(["Ministry", "Service", "Division"])
    assert list(OrgLevel.objects.values_list("name", flat=True)) == ["Ministry", "Service", "Division"]
    with pytest.raises(svc.StructureError) as e:
        svc.delete_level(OrgLevel.objects.get(depth=1))
    assert e.value.code in ("level_in_use", "level_not_last")
    svc.delete_level(OrgLevel.objects.get(depth=2))
    group = OfficeGroup.objects.create(name="Mainland")
    svc.set_group_members(group, [o["A"].pk, o["B"].pk])
    svc.set_group_members(group, [o["B"].pk])
    assert list(group.members.values_list("office__code", flat=True)) == ["B"]

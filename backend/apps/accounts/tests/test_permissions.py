import pytest
from django.http import Http404

from apps.accounts import permissions as perm
from apps.tenancy import context
from tests.factories import assign, make_agency, make_office, make_root, make_user

pytestmark = pytest.mark.django_db


@pytest.fixture
def tree():
    """root ─┬─ div1 ─ unit1
    └─ div2"""
    agency = make_agency("alpha")
    root = make_root(agency)
    div1 = make_office(root, "DIV1")
    div2 = make_office(root, "DIV2")
    unit1 = make_office(div1, "UNIT1")
    return agency, root, div1, div2, unit1


def test_paths(tree):
    _, root, div1, _, unit1 = tree
    assert unit1.path == f"/{root.id}/{div1.id}/{unit1.id}/"
    assert unit1.depth == 2 and unit1.ancestor_ids == [str(root.id), str(div1.id)]


def test_agency_admin(tree):
    agency, root, div1, div2, unit1 = tree
    boss = make_user(agency, "boss@alpha.gov")
    assign(boss, root, "admin")
    with context.agency_context(agency.id):
        assert perm.is_agency_admin(boss)
        assert set(perm.scope(boss)) == {root, div1, div2, unit1}
        assert all(perm.can_edit(boss, o) for o in (root, div1, div2, unit1))


def test_mid_level_admin_cannot_see_or_edit_sibling(tree):
    agency, root, div1, div2, unit1 = tree
    head = make_user(agency, "head@alpha.gov")
    assign(head, div1, "admin")
    with context.agency_context(agency.id):
        assert not perm.is_agency_admin(head)
        assert set(perm.scope(head)) == {div1, unit1}
        assert perm.can_edit(head, unit1) and perm.can_edit(head, div1)
        assert not perm.can_view(head, div2) and not perm.can_edit(head, div2)
        assert not perm.can_view(head, root)
        with pytest.raises(Http404):
            perm.get_office_or_404(head, div2.id)
        assert perm.get_office_or_404(head, unit1.id, edit=True) == unit1


def test_read_only_and_mixed_assignments(tree):
    agency, root, div1, div2, unit1 = tree
    viewer = make_user(agency, "viewer@alpha.gov")
    assign(viewer, root, "read_only")
    assign(viewer, div2, "admin")
    with context.agency_context(agency.id):
        assert not perm.is_agency_admin(viewer)  # read-only at root is not agency admin
        assert perm.can_view(viewer, unit1) and not perm.can_edit(viewer, unit1)
        assert perm.can_edit(viewer, div2)
        assert set(perm.edit_scope(viewer)) == {div2}
        with pytest.raises(Http404):
            perm.get_office_or_404(viewer, unit1.id, edit=True)


def test_no_assignment_means_no_scope(tree):
    agency, root, *_ = tree
    nobody = make_user(agency, "nobody@alpha.gov")
    with context.agency_context(agency.id):
        assert list(perm.scope(nobody)) == []
        assert not perm.can_view(nobody, root)
        with pytest.raises(Http404):
            perm.get_office_or_404(nobody, "not-a-uuid")


def test_path_prefix_does_not_leak_between_similar_ids(tree):
    """Paths end with '/', so one office's path is never a prefix of an unrelated office's path."""
    _, root, div1, div2, _ = tree
    assert not div2.path.startswith(div1.path)

"""Structure rules (MASTERPLAN 6.3, P2.1): one root per agency, no cycles, subtree moves rewrite
``path`` in one statement, an office's level always matches its depth, offices in use are
deactivated rather than deleted.

All functions run under the caller's agency context; every office they read goes through the
RLS-scoped manager, so an id from another agency is simply "not found".
"""

from django.db import IntegrityError, connection, transaction
from django.db.models import Max, ProtectedError

from apps.audit import services as audit
from apps.structure.models import Office, OfficeGroup, OfficeGroupMember, OrgLevel


class StructureError(Exception):
    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code
        self.message = message


def level_for_depth(depth: int) -> OrgLevel:
    level = OrgLevel.objects.filter(depth=depth).first()
    if level is None:
        level = OrgLevel.objects.create(depth=depth, name=f"Level {depth}")
    return level


def get_root() -> Office | None:
    return Office.objects.filter(parent__isnull=True).first()


def _check_code(code: str, exclude_id=None) -> str:
    code = (code or "").strip()
    if not code:
        raise StructureError("code_required", "Every office needs a code.")
    if len(code) > 40:
        raise StructureError("code_too_long", "Office codes have at most 40 characters.")
    qs = Office.objects.filter(code__iexact=code)
    if exclude_id:
        qs = qs.exclude(pk=exclude_id)
    if qs.exists():
        raise StructureError("duplicate_code", f"Another office already uses the code '{code}'.")
    return code


def create_root(name: str, code: str, level_name: str = "Agency") -> Office:
    if get_root() is not None:
        raise StructureError("root_exists", "This agency already has its top office.")
    level = OrgLevel.objects.filter(depth=0).first() or OrgLevel.objects.create(depth=0, name=level_name)
    return Office.objects.create(level=level, name=name.strip(), code=_check_code(code))


def create_office(parent: Office, name: str, code: str, sort_order: int | None = None) -> Office:
    if not (name or "").strip():
        raise StructureError("name_required", "Every office needs a name.")
    if sort_order is None:
        sort_order = (Office.objects.filter(parent=parent).aggregate(m=Max("sort_order"))["m"] or 0) + 10
    office = Office(
        parent=parent,
        level=level_for_depth(parent.depth + 1),
        name=name.strip(),
        code=_check_code(code),
        sort_order=sort_order,
    )
    try:
        with transaction.atomic():
            office.save()
    except IntegrityError as exc:
        raise StructureError("duplicate_code", f"Another office already uses the code '{code}'.") from exc
    return office


def rename_office(office: Office, *, name: str | None = None, code: str | None = None) -> Office:
    fields = []
    if name is not None:
        if not name.strip():
            raise StructureError("name_required", "Every office needs a name.")
        office.name = name.strip()
        fields.append("name")
    if code is not None:
        office.code = _check_code(code, exclude_id=office.pk)
        fields.append("code")
    if fields:
        office.save(update_fields=fields)
    return office


def subtree(office: Office):
    return Office.objects.filter(path__startswith=office.path)


@transaction.atomic
def move_office(office: Office, new_parent: Office) -> Office:
    """Move ``office`` and its subtree under ``new_parent``: paths and levels in one transaction."""
    if office.parent_id is None:
        raise StructureError("cannot_move_root", "The top office cannot be moved.")
    if new_parent.path.startswith(office.path):
        raise StructureError("cycle", "An office cannot be moved under itself or one of its own offices.")
    if office.parent_id == new_parent.pk:
        return office
    old_prefix = office.path
    old_parent_id = office.parent_id
    new_prefix = f"{new_parent.path}{office.pk}/"
    depth_shift = (new_parent.depth + 1) - office.depth
    # Lock the subtree, then rewrite every path with one statement.
    list(subtree(office).select_for_update().values_list("pk", flat=True))
    office.parent = new_parent
    with audit.suppressed():  # one "move" event below instead of a bare parent update
        office.save(update_fields=["parent"])
    with connection.cursor() as cur:
        cur.execute(
            "UPDATE office SET path = %s || substr(path, %s) WHERE path LIKE %s",
            [new_prefix, len(old_prefix) + 1, old_prefix.replace("%", r"\%") + "%"],
        )
    if depth_shift:
        for moved in Office.objects.filter(path__startswith=new_prefix).only("id", "path"):
            level = level_for_depth(moved.depth)
            Office.objects.filter(pk=moved.pk).update(level=level)
    office.refresh_from_db()
    moved_count = subtree(office).count()
    audit.record(
        "move",
        office,
        before={"parent_id": old_parent_id},
        after={"parent_id": new_parent.pk, "offices_moved": moved_count},
    )
    return office


@transaction.atomic
def reorder_children(parent: Office, ordered_ids: list) -> None:
    children = {str(o.pk): o for o in Office.objects.filter(parent=parent)}
    wanted = [str(i) for i in ordered_ids]
    if set(wanted) != set(children):
        raise StructureError("bad_order", "The new order must list every child office exactly once.")
    before = [str(o.pk) for o in sorted(children.values(), key=lambda o: (o.sort_order, o.name))]
    for position, office_id in enumerate(wanted):
        Office.objects.filter(pk=office_id).update(sort_order=(position + 1) * 10)
    audit.record("reorder", parent, before={"order": before}, after={"order": wanted})


def set_active(office: Office, active: bool) -> Office:
    if office.parent_id is None and not active:
        raise StructureError("cannot_deactivate_root", "The top office cannot be deactivated.")
    if active and office.parent and not office.parent.is_active:
        raise StructureError("parent_inactive", "Reactivate the parent office first.")
    if not active:
        affected = [str(i) for i in subtree(office).filter(is_active=True).values_list("pk", flat=True)]
        subtree(office).update(is_active=False)
        audit.record(
            "deactivate", office, before={"is_active": True}, after={"is_active": False, "offices": affected}
        )
    else:
        office.is_active = True
        with audit.suppressed():
            office.save(update_fields=["is_active"])
        audit.record("activate", office, before={"is_active": False}, after={"is_active": True})
    office.refresh_from_db()
    return office


@transaction.atomic
def delete_office(office: Office) -> None:
    """Delete an unused leaf office. Offices with children, plans or submissions are only
    deactivated (6.3): plan and submission tables reference office with ON DELETE PROTECT."""
    if office.parent_id is None:
        raise StructureError("cannot_delete_root", "The top office cannot be deleted.")
    if Office.objects.filter(parent=office).exists():
        raise StructureError("has_children", "Remove or move its offices first, or deactivate it instead.")
    try:
        with transaction.atomic():
            office.delete()
    except (ProtectedError, IntegrityError) as exc:
        raise StructureError("in_use", "This office has plans or reports. Deactivate it instead.") from exc


# ---- Levels ----------------------------------------------------------------------------------


def rename_level(level: OrgLevel, name: str) -> OrgLevel:
    if not (name or "").strip():
        raise StructureError("name_required", "Every level needs a name.")
    level.name = name.strip()
    level.save(update_fields=["name"])
    return level


def set_level_names(names: list[str]) -> list[OrgLevel]:
    """Set the names of levels 0..n-1 (the setup wizard's first step). Creates missing levels."""
    out = []
    for depth, name in enumerate(names):
        if not (name or "").strip():
            raise StructureError("name_required", f"Level {depth} needs a name.")
        level, _ = OrgLevel.objects.get_or_create(depth=depth, defaults={"name": name.strip()})
        if level.name != name.strip():
            rename_level(level, name)
        out.append(level)
    return out


def delete_level(level: OrgLevel) -> None:
    if level.offices.exists():
        raise StructureError("level_in_use", "Offices are at this level; it cannot be removed.")
    if OrgLevel.objects.filter(depth__gt=level.depth).exists():
        raise StructureError("level_not_last", "Only the deepest level can be removed.")
    level.delete()


# ---- Groups ----------------------------------------------------------------------------------


def set_group_members(group: OfficeGroup, office_ids: list) -> None:
    offices = list(Office.objects.filter(pk__in=office_ids))
    if len(offices) != len(set(map(str, office_ids))):
        raise StructureError("unknown_office", "One or more offices do not exist.")
    with transaction.atomic():
        before = sorted(
            str(i) for i in OfficeGroupMember.objects.filter(group=group).values_list("office_id", flat=True)
        )
        with audit.suppressed():  # one "group_members" event instead of one row per member
            OfficeGroupMember.objects.filter(group=group).exclude(office__in=offices).delete()
            existing = set(OfficeGroupMember.objects.filter(group=group).values_list("office_id", flat=True))
            OfficeGroupMember.objects.bulk_create(
                [OfficeGroupMember(group=group, office=o) for o in offices if o.pk not in existing]
            )
        after = sorted(str(o.pk) for o in offices)
        if before != after:
            audit.record("group_members", group, before={"offices": before}, after={"offices": after})


# ---- Paste-a-list import (P2.3) ----------------------------------------------------------------


def plan_import(base_parent: Office, rows: list[dict]) -> tuple[list[dict], list[dict]]:
    """Validate rows ``{code, name, depth?, parent_code?}`` for creation under ``base_parent``.

    ``parent_code`` (an existing office or an earlier row) wins over ``depth``; otherwise a row of
    depth d hangs under the last row of depth d-1, and depth 0 hangs under ``base_parent``.
    Returns (resolved rows with ``parent_code`` filled, errors ``{row, message}``). Nothing is
    created here.
    """
    existing = {o.code.upper(): o for o in Office.objects.all()}
    seen: dict[str, int] = {}
    last_at_depth: dict[int, str] = {}
    resolved, errors = [], []
    for i, raw in enumerate(rows, start=1):
        code = str(raw.get("code") or "").strip()
        name = str(raw.get("name") or "").strip()
        depth = int(raw.get("depth") or 0)
        parent_code = str(raw.get("parent_code") or "").strip()
        problems = []
        if not code:
            problems.append("code is missing")
        elif len(code) > 40:
            problems.append("code is longer than 40 characters")
        elif code.upper() in existing:
            problems.append(f"code {code} is already used by an office")
        elif code.upper() in seen:
            problems.append(f"code {code} also appears on row {seen[code.upper()]}")
        if not name:
            problems.append("name is missing")
        if parent_code:
            if parent_code.upper() not in existing and parent_code.upper() not in seen:
                problems.append(f"parent {parent_code} is not an existing office or an earlier row")
        elif depth == 0:
            parent_code = base_parent.code
        elif depth - 1 in last_at_depth:
            parent_code = last_at_depth[depth - 1]
        else:
            problems.append("indented further than the row above")
        for message in problems:
            errors.append({"row": i, "message": message})
        if code:
            seen.setdefault(code.upper(), i)
            last_at_depth[depth] = code
            for deeper in [d for d in last_at_depth if d > depth]:
                del last_at_depth[deeper]
        resolved.append({"row": i, "code": code, "name": name, "parent_code": parent_code})
    return resolved, errors


@transaction.atomic
def run_import(base_parent: Office, rows: list[dict]) -> list[Office]:
    resolved, errors = plan_import(base_parent, rows)
    if errors:
        raise StructureError("import_invalid", f"{len(errors)} problem(s) found; nothing was imported.")
    by_code = {o.code.upper(): o for o in Office.objects.all()}
    created = []
    for row in resolved:
        office = create_office(by_code[row["parent_code"].upper()], row["name"], row["code"])
        by_code[office.code.upper()] = office
        created.append(office)
    return created

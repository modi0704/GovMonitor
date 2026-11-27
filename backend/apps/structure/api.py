"""Structure API (MASTERPLAN 13: levels, offices (tree, move), groups) — P2.2, P2.6.

Reads are filtered by ``scope(user)``; every change is for the agency administrator only (6.6).
Ids outside the caller's scope (or agency) answer 404.
"""

from django.http import Http404
from rest_framework import serializers, status
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts import permissions as perm
from apps.accounts.permissions import IsAgencyAdmin, ReadOrAgencyAdmin
from apps.structure import services as svc
from apps.structure.models import Office, OfficeGroup, OfficeGroupMember, OrgLevel


def error(err: svc.StructureError) -> Response:
    return Response({"detail": err.message, "code": err.code}, status=status.HTTP_400_BAD_REQUEST)


def level_payload(level: OrgLevel, counts: dict | None = None) -> dict:
    return {
        "id": str(level.id),
        "depth": level.depth,
        "name": level.name,
        "office_count": (counts or {}).get(level.id, 0),
    }


def office_payload(office: Office, user=None, levels: dict | None = None) -> dict:
    level = (levels or {}).get(office.level_id) or office.level
    return {
        "id": str(office.id),
        "parent_id": str(office.parent_id) if office.parent_id else None,
        "code": office.code,
        "name": office.name,
        "depth": office.depth,
        "level": {"id": str(level.id), "name": level.name, "depth": level.depth},
        "sort_order": office.sort_order,
        "is_active": office.is_active,
        "can_edit": perm.can_edit(user, office) if user else False,
    }


def group_payload(group: OfficeGroup, visible_ids: set | None = None) -> dict:
    members = [
        m.office
        for m in group.members.select_related("office").order_by("office__sort_order", "office__name")
    ]
    if visible_ids is not None:
        members = [o for o in members if o.id in visible_ids]
    return {
        "id": str(group.id),
        "name": group.name,
        "description": group.description,
        "sort_order": group.sort_order,
        "members": [
            {"id": str(o.id), "code": o.code, "name": o.name, "is_active": o.is_active} for o in members
        ],
    }


def scoped_office(request, office_id, *, edit=False) -> Office:
    return perm.get_office_or_404(request.user, office_id, edit=edit)


# ---- Levels -------------------------------------------------------------------------------------


class LevelListView(APIView):
    permission_classes = [ReadOrAgencyAdmin]

    def get(self, request):
        from django.db.models import Count

        counts = dict(OrgLevel.objects.annotate(n=Count("offices")).values_list("id", "n"))
        return Response([level_payload(lv, counts) for lv in OrgLevel.objects.order_by("depth")])

    def put(self, request):
        """Set the names of levels 0..n-1: ``{"names": ["Ministry", "Service", "Division"]}``."""
        names = request.data.get("names")
        if not isinstance(names, list) or not names:
            return Response({"names": ["Give at least one level name."]}, status=400)
        try:
            svc.set_level_names([str(n) for n in names])
        except svc.StructureError as err:
            return error(err)
        return self.get(request)


class LevelDetailView(APIView):
    permission_classes = [IsAgencyAdmin]

    def _get(self, level_id):
        level = OrgLevel.objects.filter(pk=level_id).first()
        if level is None:
            raise Http404()
        return level

    def patch(self, request, level_id):
        try:
            level = svc.rename_level(self._get(level_id), str(request.data.get("name", "")))
        except svc.StructureError as err:
            return error(err)
        return Response(level_payload(level))

    def delete(self, request, level_id):
        try:
            svc.delete_level(self._get(level_id))
        except svc.StructureError as err:
            return error(err)
        return Response(status=status.HTTP_204_NO_CONTENT)


# ---- Offices ------------------------------------------------------------------------------------


class OfficeCreateSerializer(serializers.Serializer):
    parent_id = serializers.UUIDField(required=False, allow_null=True)
    name = serializers.CharField(max_length=200)
    code = serializers.CharField(max_length=40)
    sort_order = serializers.IntegerField(required=False)


class OfficeTreeView(APIView):
    """GET: every office in the caller's scope, in tree order, in one call. POST: create."""

    permission_classes = [ReadOrAgencyAdmin]

    def get(self, request):
        levels = {lv.id: lv for lv in OrgLevel.objects.all()}
        offices = perm.scope(request.user).order_by("path")
        include_inactive = request.query_params.get("include_inactive", "1") != "0"
        if not include_inactive:
            offices = offices.filter(is_active=True)
        rows = [office_payload(o, request.user, levels) for o in offices]
        # Tree order with siblings by sort_order: sort by the chain of (sort_order, name) keys.
        by_id = {r["id"]: r for r in rows}

        def key(row):
            chain, cur = [], row
            while cur is not None:
                chain.append((cur["sort_order"], cur["name"].lower(), cur["id"]))
                cur = by_id.get(cur["parent_id"])
            return list(reversed(chain))

        rows.sort(key=key)
        return Response(rows)

    def post(self, request):
        s = OfficeCreateSerializer(data=request.data)
        s.is_valid(raise_exception=True)
        d = s.validated_data
        try:
            if d.get("parent_id") is None:
                office = svc.create_root(d["name"], d["code"])
            else:
                parent = scoped_office(request, d["parent_id"], edit=True)
                office = svc.create_office(parent, d["name"], d["code"], d.get("sort_order"))
        except svc.StructureError as err:
            return error(err)
        return Response(office_payload(office, request.user), status=status.HTTP_201_CREATED)


class OfficeDetailView(APIView):
    permission_classes = [ReadOrAgencyAdmin]

    def get(self, request, office_id):
        office = scoped_office(request, office_id)
        payload = office_payload(office, request.user)
        payload["ancestors"] = [
            {"id": str(o.id), "code": o.code, "name": o.name}
            for o in perm.scope(request.user).filter(pk__in=office.ancestor_ids).order_by("path")
        ]
        return Response(payload)

    def patch(self, request, office_id):
        office = scoped_office(request, office_id, edit=True)
        try:
            if "name" in request.data or "code" in request.data:
                svc.rename_office(office, name=request.data.get("name"), code=request.data.get("code"))
            if "is_active" in request.data:
                svc.set_active(office, bool(request.data["is_active"]))
        except svc.StructureError as err:
            return error(err)
        office.refresh_from_db()
        return Response(office_payload(office, request.user))

    def delete(self, request, office_id):
        """Delete an unused office; with ``?everything=1``, the office, every office beneath it and
        everything recorded for them (see ``delete-preview``)."""
        office = scoped_office(request, office_id, edit=True)
        try:
            if request.query_params.get("everything") == "1":
                return Response(svc.delete_office_and_contents(office))
            svc.delete_office(office)
        except svc.StructureError as err:
            return error(err)
        return Response(status=status.HTTP_204_NO_CONTENT)


class OfficeDeletePreviewView(APIView):
    """GET — what deleting this office with everything recorded for it would remove."""

    permission_classes = [IsAgencyAdmin]

    def get(self, request, office_id):
        office = scoped_office(request, office_id, edit=True)
        if office.parent_id is None:
            return error(svc.StructureError("cannot_delete_root", "The top office cannot be deleted."))
        return Response(svc.deletion_preview(office))


class OfficeMoveView(APIView):
    permission_classes = [IsAgencyAdmin]

    def post(self, request, office_id):
        office = scoped_office(request, office_id, edit=True)
        parent = scoped_office(request, request.data.get("parent_id"), edit=True)
        try:
            office = svc.move_office(office, parent)
        except svc.StructureError as err:
            return error(err)
        return Response(office_payload(office, request.user))


class OfficeReorderView(APIView):
    permission_classes = [IsAgencyAdmin]

    def post(self, request):
        parent = scoped_office(request, request.data.get("parent_id"), edit=True)
        order = request.data.get("order")
        if not isinstance(order, list):
            return Response({"order": ["Give the child office ids in their new order."]}, status=400)
        try:
            svc.reorder_children(parent, order)
        except svc.StructureError as err:
            return error(err)
        return Response(status=status.HTTP_204_NO_CONTENT)


# ---- Groups -------------------------------------------------------------------------------------


class GroupSerializer(serializers.Serializer):
    name = serializers.CharField(max_length=120)
    description = serializers.CharField(required=False, allow_blank=True, default="")
    sort_order = serializers.IntegerField(required=False, default=0)


def _visible_ids(user) -> set:
    return set(perm.scope(user).values_list("id", flat=True))


class GroupListView(APIView):
    permission_classes = [ReadOrAgencyAdmin]

    def get(self, request):
        visible = _visible_ids(request.user)
        groups = OfficeGroup.objects.prefetch_related("members__office")
        if not perm.is_agency_admin(request.user):
            # A group is shown when at least one of its members is in the caller's scope.
            groups = groups.filter(members__office_id__in=visible).distinct()
        return Response([group_payload(g, visible) for g in groups])

    def post(self, request):
        s = GroupSerializer(data=request.data)
        s.is_valid(raise_exception=True)
        if OfficeGroup.objects.filter(name__iexact=s.validated_data["name"]).exists():
            return Response({"name": ["A group with this name already exists."]}, status=400)
        group = OfficeGroup.objects.create(**s.validated_data)
        return Response(group_payload(group), status=status.HTTP_201_CREATED)


class GroupDetailView(APIView):
    permission_classes = [ReadOrAgencyAdmin]

    def _get(self, request, group_id) -> OfficeGroup:
        group = OfficeGroup.objects.filter(pk=group_id).first()
        if group is None:
            raise Http404()
        if (
            not perm.is_agency_admin(request.user)
            and not OfficeGroupMember.objects.filter(
                group=group, office__in=perm.scope(request.user)
            ).exists()
        ):
            raise Http404()
        return group

    def get(self, request, group_id):
        return Response(group_payload(self._get(request, group_id), _visible_ids(request.user)))

    def patch(self, request, group_id):
        group = self._get(request, group_id)
        s = GroupSerializer(group, data={**GroupSerializer(group).data, **request.data})
        s.is_valid(raise_exception=True)
        for k, v in s.validated_data.items():
            setattr(group, k, v)
        group.save()
        return Response(group_payload(group))

    def delete(self, request, group_id):
        self._get(request, group_id).delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class GroupMembersView(APIView):
    permission_classes = [IsAgencyAdmin]

    def put(self, request, group_id):
        group = OfficeGroup.objects.filter(pk=group_id).first()
        if group is None:
            raise Http404()
        ids = request.data.get("office_ids")
        if not isinstance(ids, list):
            return Response({"office_ids": ["Give a list of office ids."]}, status=400)
        try:
            svc.set_group_members(group, ids)
        except svc.StructureError as err:
            return error(err)
        except Exception:  # noqa: BLE001 — malformed ids
            return Response({"office_ids": ["One or more ids are not valid."]}, status=400)
        return Response(group_payload(group))


class OfficeImportView(APIView):
    """Paste-a-list import. ``{"parent_id", "rows": [{code, name, depth, parent_code}], "dry_run"}``.

    A dry run returns the resolved preview and every problem; a real run creates all rows or none.
    """

    permission_classes = [IsAgencyAdmin]

    def post(self, request):
        parent = scoped_office(request, request.data.get("parent_id"), edit=True)
        rows = request.data.get("rows")
        if not isinstance(rows, list) or not rows:
            return Response({"rows": ["Paste at least one office."]}, status=400)
        if len(rows) > 2000:
            return Response({"rows": ["At most 2,000 offices per import."]}, status=400)
        resolved, errors = svc.plan_import(parent, rows)
        if request.data.get("dry_run") or errors:
            return Response(
                {"rows": resolved, "errors": errors, "created": 0},
                status=status.HTTP_200_OK if not errors or request.data.get("dry_run") else 400,
            )
        created = svc.run_import(parent, rows)
        return Response(
            {"rows": resolved, "errors": [], "created": len(created)}, status=status.HTTP_201_CREATED
        )


class OfficeDirectoryView(APIView):
    """Code and name of every active office in the agency — for pick-lists such as the implementing
    office of an activity, which may lie outside the user's own scope (D29). No other data."""

    def get(self, request):
        offices = Office.objects.filter(is_active=True).order_by("path")
        return Response(
            [{"id": str(o.id), "code": o.code, "name": o.name, "depth": o.depth} for o in offices]
        )

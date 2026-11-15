"""Audit log API for the agency administrator (P3.5): filter, row detail, CSV download."""

import csv
import datetime
import io
import json

from django.http import Http404, HttpResponse
from django.utils import timezone
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.permissions import IsAgencyAdmin
from apps.audit import services as audit
from apps.audit.models import AuditLog
from apps.structure.models import Office

PAGE_SIZE = 50
CSV_LIMIT = 100_000


def row_payload(row: AuditLog, detail: bool = False) -> dict:
    out = {
        "id": row.id,
        "at": row.at.isoformat(),
        "actor_type": row.actor_type,
        "actor_id": str(row.actor_id) if row.actor_id else None,
        "actor": row.actor_label or row.actor_type,
        "action": row.action,
        "entity_type": row.entity_type,
        "entity_id": row.entity_id,
        "office_id": str(row.office_id) if row.office_id else None,
        "ip": row.ip,
        "changed": sorted(set((row.before or {}).keys()) | set((row.after or {}).keys())),
    }
    if detail:
        out.update(before=row.before, after=row.after, user_agent=row.user_agent, request_id=row.request_id)
    return out


def _parse_date(value: str | None, end: bool = False):
    if not value:
        return None
    try:
        day = datetime.date.fromisoformat(value)
    except ValueError:
        return None
    moment = datetime.datetime.combine(day, datetime.time.max if end else datetime.time.min)
    return timezone.make_aware(moment, datetime.UTC)


def filtered(params):
    qs = AuditLog.objects.all()
    if start := _parse_date(params.get("from")):
        qs = qs.filter(at__gte=start)
    if end := _parse_date(params.get("to"), end=True):
        qs = qs.filter(at__lte=end)
    if actor := params.get("actor"):
        qs = qs.filter(actor_id=actor)
    if action := params.get("action"):
        qs = qs.filter(action=action)
    if entity_type := params.get("entity_type"):
        qs = qs.filter(entity_type=entity_type)
    if entity_id := params.get("entity_id"):
        qs = qs.filter(entity_id=entity_id)
    if office := params.get("office"):
        root = Office.objects.filter(pk=office).first()
        ids = (
            list(Office.objects.filter(path__startswith=root.path).values_list("id", flat=True))
            if root
            else []
        )
        qs = qs.filter(office_id__in=ids)
    return qs


def _safe(view, request):
    try:
        return filtered(request.query_params)
    except Exception as exc:  # noqa: BLE001 — malformed uuid filters
        raise Http404() from exc


class AuditLogListView(APIView):
    permission_classes = [IsAgencyAdmin]

    def get(self, request):
        qs = _safe(self, request).order_by("-id")
        before = request.query_params.get("before")
        if before and before.isdigit():
            qs = qs.filter(id__lt=int(before))
        rows = list(qs[: PAGE_SIZE + 1])
        more = len(rows) > PAGE_SIZE
        rows = rows[:PAGE_SIZE]
        return Response(
            {
                "results": [row_payload(r) for r in rows],
                "next_before": rows[-1].id if more else None,
                "actions": sorted(AuditLog.objects.values_list("action", flat=True).distinct()),
                "entity_types": sorted(
                    t for t in AuditLog.objects.values_list("entity_type", flat=True).distinct() if t
                ),
            }
        )


class AuditLogDetailView(APIView):
    permission_classes = [IsAgencyAdmin]

    def get(self, request, row_id):
        row = AuditLog.objects.filter(pk=row_id).first()
        if row is None:
            raise Http404()
        return Response(row_payload(row, detail=True))


class AuditLogCsvView(APIView):
    """CSV of the filtered log. The download itself is audited as ``export``."""

    permission_classes = [IsAgencyAdmin]

    def get(self, request):
        qs = _safe(self, request).order_by("id")[:CSV_LIMIT]
        buf = io.StringIO()
        writer = csv.writer(buf)
        writer.writerow(
            [
                "id",
                "at_utc",
                "actor_type",
                "actor",
                "action",
                "entity_type",
                "entity_id",
                "office_id",
                "ip",
                "request_id",
                "before",
                "after",
            ]
        )
        count = 0
        for r in qs.iterator(chunk_size=2000):
            count += 1
            writer.writerow(
                [
                    r.id,
                    r.at.isoformat(),
                    r.actor_type,
                    r.actor_label,
                    r.action,
                    r.entity_type,
                    r.entity_id,
                    r.office_id or "",
                    r.ip or "",
                    r.request_id,
                    json.dumps(r.before, ensure_ascii=False) if r.before is not None else "",
                    json.dumps(r.after, ensure_ascii=False) if r.after is not None else "",
                ]
            )
        filters = {k: v for k, v in request.query_params.items() if v}
        audit.record(
            "export", entity_type="audit_log", after={"format": "csv", "rows": count, "filters": filters}
        )
        response = HttpResponse(buf.getvalue(), content_type="text/csv; charset=utf-8")
        stamp = timezone.now().strftime("%Y%m%d-%H%M")
        response["Content-Disposition"] = f'attachment; filename="audit-log-{stamp}.csv"'
        return response

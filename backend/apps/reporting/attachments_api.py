"""Supporting files (MOVs): upload, list, authorised download, soft delete (P6.2, P6.6, P12.2)."""

from django.core.files.storage import default_storage
from django.db import transaction
from django.http import FileResponse, Http404
from django.utils import timezone
from rest_framework import status
from rest_framework.parsers import MultiPartParser
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts import permissions as perm
from apps.audit import services as audit
from apps.planning.models import ReportingPeriod
from apps.reporting import files, rules
from apps.reporting.models import ActivityActual, Attachment, IndicatorActual


def error(err) -> Response:
    return Response({"detail": err.message, "code": err.code}, status=getattr(err, "http", 400))


def attachment_payload(a: Attachment) -> dict:
    return {
        "id": str(a.id),
        "target_type": a.target_type,
        "target_id": str(a.target_id),
        "file_name": a.file_name,
        "content_type": a.content_type,
        "size_bytes": a.size_bytes,
        "sha256": a.sha256,
        "description": a.description,
        "uploaded_by": a.uploaded_by.email if a.uploaded_by_id else None,
        "uploaded_at": a.uploaded_at.isoformat(),
        "download_url": f"/api/v1/attachments/{a.id}/download",
    }


def _period(period_id) -> ReportingPeriod:
    period = ReportingPeriod.objects.filter(pk=period_id).first() if period_id else None
    if period is None:
        raise Http404()
    return period


def resolve_target(user, target_type: str, lineage_id, period: ReportingPeriod, *, edit: bool):
    """Find (or, when editing, create) the actual row a file belongs to; enforce P6.4 rules."""
    if target_type == Attachment.TargetType.ACTIVITY_ACTUAL:
        ref = rules.activity_in_period(lineage_id, period)
        if ref is None or not rules.can_view_activity(user, ref):
            raise Http404()
        if edit:
            rules.check_can_report_activity(user, ref, period)
            actual, _ = ActivityActual.objects.get_or_create(
                activity_lineage_id=lineage_id,
                period=period,
                defaults={"office": ref.owner_office, "entered_by": user},
            )
        else:
            actual = ActivityActual.objects.filter(activity_lineage_id=lineage_id, period=period).first()
        return actual, ref.owner_office
    if target_type == Attachment.TargetType.INDICATOR_ACTUAL:
        ind = rules.indicator_in_period(lineage_id, period)
        if ind is None or not perm.can_view(user, ind.plan.office):
            raise Http404()
        if edit:
            if not perm.can_edit(user, ind.plan.office):
                raise rules.ReportingError("read_only", "You have read-only access to this office.", http=403)
            rules.check_period_open(period)
            rules.check_submission_editable(ind.plan.office, period)
            actual, _ = IndicatorActual.objects.get_or_create(
                indicator_lineage_id=lineage_id,
                period=period,
                defaults={"office": ind.plan.office, "entered_by": user},
            )
        else:
            actual = IndicatorActual.objects.filter(indicator_lineage_id=lineage_id, period=period).first()
        return actual, ind.plan.office
    raise rules.ReportingError("bad_target", "target_type must be activity_actual or indicator_actual.")


def visible_attachment(user, attachment_id) -> Attachment:
    a = (
        Attachment.objects.select_related("office", "uploaded_by")
        .filter(pk=attachment_id, deleted_at=None)
        .first()
    )
    if a is None:
        raise Http404()
    if perm.can_view(user, a.office):
        return a
    # Implementing offices may see files on activities they carry out.
    if a.target_type == Attachment.TargetType.ACTIVITY_ACTUAL:
        actual = ActivityActual.objects.filter(pk=a.target_id).first()
        ref = rules.activity_in_period(actual.activity_lineage_id, a.period) if actual else None
        if ref and rules.can_view_activity(user, ref):
            return a
    raise Http404()


class AttachmentListView(APIView):
    """GET ?target_type&lineage_id&period_id — files of one actual. POST multipart — upload one file."""

    parser_classes = [MultiPartParser]

    def get(self, request):
        p = request.query_params
        try:
            period = _period(p.get("period_id"))
            actual, _ = resolve_target(
                request.user, p.get("target_type", ""), p.get("lineage_id"), period, edit=False
            )
        except rules.ReportingError as err:
            return error(err)
        except (ValueError, TypeError) as exc:
            raise Http404() from exc
        if actual is None:
            return Response([])
        rows = Attachment.objects.select_related("uploaded_by").filter(target_id=actual.pk, deleted_at=None)
        return Response([attachment_payload(a) for a in rows.order_by("uploaded_at")])

    @transaction.atomic
    def post(self, request):
        upload = request.FILES.get("file")
        if upload is None:
            return Response({"file": ["Choose a file to attach."]}, status=400)
        d = request.data
        try:
            period = _period(d.get("period_id"))
            actual, office = resolve_target(
                request.user, d.get("target_type", ""), d.get("lineage_id"), period, edit=True
            )
            stored = files.store(upload, request.user.agency_id)
        except (rules.ReportingError, files.UploadError) as err:
            return error(err)
        attachment = Attachment.objects.create(
            target_type=d.get("target_type"),
            target_id=actual.pk,
            office=office,
            period=period,
            description=str(d.get("description", ""))[:500],
            uploaded_by=request.user,
            **stored,
        )
        return Response(attachment_payload(attachment), status=status.HTTP_201_CREATED)


class AttachmentDownloadView(APIView):
    def get(self, request, attachment_id):
        a = visible_attachment(request.user, attachment_id)
        try:
            handle = default_storage.open(a.storage_key, "rb")
        except (FileNotFoundError, OSError) as exc:
            raise Http404("The stored file is missing.") from exc
        audit.record("download", a, after={"file_name": a.file_name})
        response = FileResponse(handle, content_type=a.content_type, as_attachment=True, filename=a.file_name)
        response["X-Content-Type-Options"] = "nosniff"
        response["Cache-Control"] = "private, no-store"
        return response


class AttachmentDetailView(APIView):
    def delete(self, request, attachment_id):
        a = visible_attachment(request.user, attachment_id)
        try:
            if a.target_type == Attachment.TargetType.ACTIVITY_ACTUAL:
                actual = ActivityActual.objects.get(pk=a.target_id)
                resolve_target(request.user, a.target_type, actual.activity_lineage_id, a.period, edit=True)
            else:
                actual = IndicatorActual.objects.get(pk=a.target_id)
                resolve_target(request.user, a.target_type, actual.indicator_lineage_id, a.period, edit=True)
        except rules.ReportingError as err:
            return error(err)
        with audit.suppressed():
            a.deleted_at = timezone.now()
            a.save(update_fields=["deleted_at"])
        audit.record("delete", a, before={"file_name": a.file_name}, after={"soft_deleted": True})
        return Response(status=status.HTTP_204_NO_CONTENT)

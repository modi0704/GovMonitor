"""Export requests (P9.1, P9.4): validate the scope, queue the job, audit the export."""

from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts import ratelimit
from apps.audit import services as audit
from apps.exports.pptx_layout import SLIDE_GROUPS
from apps.exports.scope import ScopeError, check_request
from apps.jobs import worker
from apps.jobs.api import job_payload
from apps.jobs.models import Job


def queue_export(request, kind: str, extra: dict | None = None) -> Response:
    try:
        params = check_request(request.user, request.data) | (extra or {})
    except ScopeError as err:
        return Response({err.field: [err.message]}, status=400)
    try:
        ratelimit.check_jobs(request.user, [Job.Kind.EXPORT_XLSX, Job.Kind.EXPORT_PPTX, Job.Kind.IMPORT_PLAN])
    except ratelimit.RateLimited as err:
        return ratelimit.too_many(err)
    with audit.suppressed():  # one meaningful "export" row instead of a generic job "create"
        job = worker.enqueue(kind, params, user=request.user)
    audit.record("export", job, after={"kind": kind, **params}, office_id=params["office_id"])
    return Response(job_payload(job), status=status.HTTP_202_ACCEPTED)


class XlsxExportView(APIView):
    """POST {scope: office|subtree|agency, office_id, period_id, view: owner|implementing}."""

    def post(self, request):
        return queue_export(request, Job.Kind.EXPORT_XLSX)


class PptxExportView(APIView):
    """POST {scope, office_id, period_id, view, groups: [overall|offices|rankings|indicators]}."""

    def post(self, request):
        groups = request.data.get("groups") or list(SLIDE_GROUPS)
        if not isinstance(groups, list) or not groups or any(g not in SLIDE_GROUPS for g in groups):
            return Response(
                {"groups": [f"Choose slide groups among: {', '.join(SLIDE_GROUPS)}."]}, status=400
            )
        ordered = [g for g in SLIDE_GROUPS if g in groups]
        return queue_export(request, Job.Kind.EXPORT_PPTX, {"groups": ordered})

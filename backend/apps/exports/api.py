"""Export requests (P9.1, P9.4): validate the scope, queue the job, audit the export."""

from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.audit import services as audit
from apps.exports.scope import ScopeError, check_request
from apps.jobs import worker
from apps.jobs.api import job_payload
from apps.jobs.models import Job


def queue_export(request, kind: str) -> Response:
    try:
        params = check_request(request.user, request.data)
    except ScopeError as err:
        return Response({err.field: [err.message]}, status=400)
    with audit.suppressed():  # one meaningful "export" row instead of a generic job "create"
        job = worker.enqueue(kind, params, user=request.user)
    audit.record("export", job, after={"kind": kind, **params}, office_id=params["office_id"])
    return Response(job_payload(job), status=status.HTTP_202_ACCEPTED)


class XlsxExportView(APIView):
    """POST {scope: office|subtree|agency, office_id, period_id, view: owner|implementing}."""

    def post(self, request):
        return queue_export(request, Job.Kind.EXPORT_XLSX)

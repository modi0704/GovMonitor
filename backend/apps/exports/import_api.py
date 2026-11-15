"""Plan import (P9.7): the template download and the upload that queues an ``import_plan`` job."""

import io
import uuid

from django.core.files.storage import default_storage
from django.http import FileResponse, Http404
from django.utils import timezone
from rest_framework import status
from rest_framework.parsers import MultiPartParser
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts import permissions as perm
from apps.audit import services as audit
from apps.exports import xlsx_writer
from apps.jobs import storage, worker
from apps.jobs.api import job_payload
from apps.jobs.models import Job
from apps.planning.models import FiscalYear, Plan
from apps.reporting import files


def _fiscal_year(fy_id) -> FiscalYear:
    try:
        fy = FiscalYear.objects.filter(pk=fy_id).first() if fy_id else None
    except (ValueError, TypeError):
        fy = None
    if fy is None:
        raise Http404("No such fiscal year.")
    return fy


class PlanTemplateView(APIView):
    """GET ?fiscal_year_id[&office_id] — the import template: the office sheet with headers only."""

    def get(self, request):
        fy = _fiscal_year(request.query_params.get("fiscal_year_id"))
        office_id = request.query_params.get("office_id")
        office = perm.get_office_or_404(request.user, office_id) if office_id else None
        data = xlsx_writer.build_template(office, fy)
        name = files.safe_name(f"plan-template-{office.code if office else 'office'}-{fy.label}.xlsx")
        return FileResponse(
            io.BytesIO(data), content_type=storage.content_type(name), as_attachment=True, filename=name
        )


class PlanImportView(APIView):
    """POST multipart {file, office_id, fiscal_year_id} — queue the import of a draft plan."""

    parser_classes = [MultiPartParser]

    def post(self, request):
        upload = request.FILES.get("file")
        if upload is None:
            return Response({"file": ["Choose the Excel file to import."]}, status=400)
        office = perm.get_office_or_404(request.user, request.data.get("office_id"), edit=True)
        fy = _fiscal_year(request.data.get("fiscal_year_id"))
        if fy.status == FiscalYear.Status.CLOSED:
            return Response({"fiscal_year_id": ["That fiscal year is closed."]}, status=400)
        if Plan.objects.filter(office=office, fiscal_year=fy).exists():
            return Response(
                {
                    "office_id": [
                        "This office already has a plan for that fiscal year; edit or revise it instead."
                    ]
                },
                status=409,
            )
        try:
            ext, _ = files.validate(upload)
        except files.UploadError as err:
            return Response({"file": [err.message]}, status=400)
        if ext != "xlsx":
            return Response({"file": ["Import an Excel workbook (.xlsx)."]}, status=400)
        stamp = f"{timezone.now():%Y}/{uuid.uuid4().hex}"
        key = f"{request.user.agency_id}/imports/{stamp}-{files.safe_name(upload.name)}"
        saved = default_storage.save(key, upload)
        params = {
            "office_id": str(office.id),
            "fiscal_year_id": str(fy.id),
            "upload_key": saved,
            "file_name": (upload.name or "plan.xlsx")[:255],
        }
        with audit.suppressed():
            job = worker.enqueue(Job.Kind.IMPORT_PLAN, params, user=request.user)
        audit.record(
            "import", job, after={k: v for k, v in params.items() if k != "upload_key"}, office_id=office.id
        )
        return Response(job_payload(job), status=status.HTTP_202_ACCEPTED)

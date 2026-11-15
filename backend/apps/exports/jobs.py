"""Export job handlers, run by the worker (P9.1)."""

import io
import re

from django.core.files.storage import default_storage

from apps.exports import scope as export_scope
from apps.exports import xlsx_writer
from apps.jobs import storage
from apps.jobs.models import Job
from apps.jobs.worker import JobRejected, handler
from apps.tenancy.models import Agency


def file_name(sc: export_scope.ExportScope, ext: str) -> str:
    agency = Agency.objects.get(pk=sc.period.agency_id)
    month = sc.period.start_date.strftime("%b-%Y")
    parts = [agency.code, sc.root.code if sc.scope != "agency" else "all", sc.fiscal_year.label, month]
    return re.sub(r"[^A-Za-z0-9._-]+", "-", "-".join(p for p in parts if p)).strip("-") + f".{ext}"


@handler(Job.Kind.EXPORT_XLSX)
def export_xlsx(job: Job) -> dict:
    sc = export_scope.resolve(job.params)
    data, summary = xlsx_writer.build(sc)
    name = file_name(sc, "xlsx")
    storage.store_result(job, name, data)
    return {"file_name": name, **summary}


@handler(Job.Kind.EXPORT_PPTX)
def export_pptx(job: Job) -> dict:
    from apps.exports import pptx_writer, templates
    from apps.exports.pptx_layout import SLIDE_GROUPS

    sc = export_scope.resolve(job.params)
    settings = templates.effective("pptx")
    data, summary = pptx_writer.build(
        sc,
        groups=tuple(job.params.get("groups") or SLIDE_GROUPS),
        settings=settings,
        logo=templates.logo_bytes(settings),
        user=job.requested_by,
    )
    name = file_name(sc, "pptx")
    storage.store_result(job, name, data)
    return {"file_name": name, "slides": summary["slides"], "offices": summary["offices"]}


@handler(Job.Kind.IMPORT_PLAN)
def import_plan(job: Job) -> dict:
    from apps.exports.plan_import import ImportFailed
    from apps.exports.plan_import import import_plan as run_import
    from apps.planning.models import FiscalYear
    from apps.structure.models import Office

    p = job.params
    office = Office.objects.get(pk=p["office_id"])
    fy = FiscalYear.objects.select_related("profile").get(pk=p["fiscal_year_id"])
    with default_storage.open(p["upload_key"], "rb") as fh:
        data = io.BytesIO(fh.read())
    try:
        result = run_import(office, fy, data)
    except ImportFailed as exc:
        raise JobRejected(
            f"{len(exc.issues)} problem(s) in the file; nothing was imported.",
            {"file_name": p["file_name"], "errors": exc.issues},
        ) from exc
    return {"file_name": p["file_name"], **result}

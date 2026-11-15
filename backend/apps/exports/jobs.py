"""Export job handlers, run by the worker (P9.1)."""

import re

from apps.exports import scope as export_scope
from apps.exports import xlsx_writer
from apps.jobs import storage
from apps.jobs.models import Job
from apps.jobs.worker import handler
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

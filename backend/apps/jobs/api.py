"""Jobs API (P9.1): poll a job, list "My exports", download a finished job's file."""

from django.core.files.storage import default_storage
from django.http import FileResponse, Http404
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts import permissions as perm
from apps.audit import services as audit
from apps.jobs import storage
from apps.jobs.models import Job

LIST_LIMIT = 50
USER_KINDS = (Job.Kind.EXPORT_XLSX, Job.Kind.EXPORT_PPTX, Job.Kind.IMPORT_PLAN)


def job_payload(job: Job) -> dict:
    done = job.status == Job.Status.DONE
    result = job.result or {}
    return {
        "id": str(job.id),
        "kind": job.kind,
        "status": job.status,
        "params": job.params,
        "result": result,
        # Users see the first line only; the traceback stays in the database for support.
        "error": (job.error.splitlines()[0] if job.error else "") if job.status == Job.Status.FAILED else "",
        "requested_by": job.requested_by.email if job.requested_by_id else None,
        "created_at": job.created_at.isoformat(),
        "finished_at": job.finished_at.isoformat() if job.finished_at else None,
        "file_name": result.get("file_name") if done and job.result_key else None,
        "download_url": f"/api/v1/jobs/{job.id}/download" if done and job.result_key else None,
    }


def visible_job(user, job_id) -> Job:
    """The requester sees their own jobs; agency admins see every job of the agency."""
    job = Job.objects.select_related("requested_by").filter(pk=job_id).first()
    if job is None or not (job.requested_by_id == user.id or perm.is_agency_admin(user)):
        raise Http404()
    return job


class JobListView(APIView):
    """GET — the signed-in user's exports and imports, newest first ("My exports")."""

    def get(self, request):
        qs = Job.objects.select_related("requested_by").filter(requested_by=request.user, kind__in=USER_KINDS)
        kind = request.query_params.get("kind")
        if kind:
            qs = qs.filter(kind=kind)
        return Response([job_payload(j) for j in qs.order_by("-created_at")[:LIST_LIMIT]])


class JobDetailView(APIView):
    def get(self, request, job_id):
        return Response(job_payload(visible_job(request.user, job_id)))


class JobDownloadView(APIView):
    def get(self, request, job_id):
        job = visible_job(request.user, job_id)
        if job.status != Job.Status.DONE or not job.result_key:
            raise Http404("This job has no file to download.")
        name = (job.result or {}).get("file_name") or job.result_key.rsplit("/", 1)[-1]
        try:
            handle = default_storage.open(job.result_key, "rb")
        except (FileNotFoundError, OSError) as exc:
            raise Http404("The file is no longer available.") from exc
        audit.record("download", job, after={"file_name": name})
        response = FileResponse(
            handle, content_type=storage.content_type(name), as_attachment=True, filename=name
        )
        response["X-Content-Type-Options"] = "nosniff"
        response["Cache-Control"] = "private, no-store"
        return response

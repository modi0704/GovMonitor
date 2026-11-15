"""Export template settings (P10.2): agency administrator only."""

import io

from django.http import FileResponse, Http404
from rest_framework.parsers import JSONParser, MultiPartParser
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.permissions import IsAgencyAdmin
from apps.exports import templates
from apps.reporting import files

KINDS = ("pptx",)


def _kind(kind: str) -> str:
    if kind not in KINDS:
        raise Http404()
    return kind


def error(err: templates.TemplateError) -> Response:
    return Response({err.field: [err.message]}, status=400)


class ExportTemplateView(APIView):
    """GET the effective settings; PATCH some of them; DELETE to go back to the system default."""

    permission_classes = [IsAgencyAdmin]

    def get(self, request, kind):
        return Response(templates.payload(_kind(kind)))

    def patch(self, request, kind):
        try:
            templates.update(_kind(kind), request.data)
        except templates.TemplateError as err:
            return error(err)
        return Response(templates.payload(kind))

    def delete(self, request, kind):
        templates.reset(_kind(kind))
        return Response(templates.payload(kind))


class ExportTemplateLogoView(APIView):
    """GET the logo; POST multipart ``file`` to replace it; DELETE to remove it."""

    permission_classes = [IsAgencyAdmin]
    parser_classes = [MultiPartParser, JSONParser]

    def get(self, request, kind):
        settings = templates.effective(_kind(kind))
        data = templates.logo_bytes(settings)
        if data is None:
            raise Http404()
        ext = settings.get("logo_type", "png")
        response = FileResponse(io.BytesIO(data), content_type=files.CONTENT_TYPES.get(ext, "image/png"))
        response["X-Content-Type-Options"] = "nosniff"
        response["Cache-Control"] = "private, no-store"
        return response

    def post(self, request, kind):
        upload = request.FILES.get("file")
        if upload is None:
            return Response({"file": ["Choose an image."]}, status=400)
        try:
            templates.set_logo(_kind(kind), upload)
        except templates.TemplateError as err:
            return error(err)
        except files.UploadError as err:
            return Response({"file": [err.message]}, status=400)
        return Response(templates.payload(kind))

    def delete(self, request, kind):
        templates.clear_logo(_kind(kind))
        return Response(templates.payload(kind))

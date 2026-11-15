from django.conf import settings
from django.http import FileResponse, HttpResponse
from django.views.decorators.csrf import ensure_csrf_cookie


@ensure_csrf_cookie
def spa_index(request, *args, **kwargs):
    """Serve the built React app's index.html for every non-API path."""
    index = settings.FRONTEND_DIST / "index.html"
    if not index.exists():
        return HttpResponse(
            "Frontend not built. Run `make build` (or `npm run build` in frontend/).",
            content_type="text/plain",
            status=503,
        )
    response = FileResponse(index.open("rb"), content_type="text/html")
    response["Cache-Control"] = "no-cache"
    return response

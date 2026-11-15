"""Which offices an export covers (MASTERPLAN 9, 10; P9.4): one office, an office and everything
beneath it, or the whole agency. Shared by the Excel and PowerPoint exports."""

from dataclasses import dataclass

from django.http import Http404

from apps.accounts import permissions as perm
from apps.planning.models import ReportingPeriod
from apps.results.agency import IMPLEMENTING, OWNER
from apps.structure.models import Office
from apps.structure.ordering import tree_key

SCOPES = ("office", "subtree", "agency")
VIEWS = (OWNER, IMPLEMENTING)


class ScopeError(Exception):
    def __init__(self, field: str, message: str):
        super().__init__(message)
        self.field = field
        self.message = message


@dataclass
class ExportScope:
    scope: str
    view: str
    period: ReportingPeriod
    root: Office  # the office the export starts from
    offices: list  # every office in scope, in tree order

    @property
    def fiscal_year(self):
        return self.period.fiscal_year

    def depth(self, office) -> int:
        return office.depth - self.root.depth


def check_request(user, data) -> dict:
    """Validate an export request for ``user``; returns the job params. 404 for offices or months
    the user may not see (never reveal existence)."""
    scope = data.get("scope") or "office"
    if scope not in SCOPES:
        raise ScopeError("scope", "Choose one office, an office and everything beneath it, or the agency.")
    view = data.get("view") or OWNER
    if view not in VIEWS:
        raise ScopeError("view", "View must be owner or implementing.")
    period_id = data.get("period_id")
    period = ReportingPeriod.objects.filter(pk=period_id).first() if period_id else None
    if period is None:
        raise ScopeError("period_id", "Choose a month.")
    if scope == "agency":
        office = Office.objects.filter(parent=None).first()
        if office is None or not perm.can_view(user, office):
            raise Http404()
    else:
        office = perm.get_office_or_404(user, data.get("office_id"))
    return {"scope": scope, "view": view, "period_id": str(period.pk), "office_id": str(office.pk)}


def resolve(params: dict) -> ExportScope:
    period = ReportingPeriod.objects.select_related("fiscal_year__profile").get(pk=params["period_id"])
    root = Office.objects.select_related("level").get(pk=params["office_id"])
    by_id = {o.id: o for o in Office.objects.select_related("level")}
    if params["scope"] == "office":
        offices = [root]
    else:
        offices = [o for o in by_id.values() if o.path.startswith(root.path)]
    offices.sort(key=lambda o: tree_key(o, by_id))
    return ExportScope(params["scope"], params.get("view", OWNER), period, root, offices)

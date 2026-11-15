"""Results API. ``results/preview`` (P5.5): engine call for unsaved grid data — weights and the
planned curve, so the plan editor never computes a score itself (rule: all scores come from
apps/scoring)."""

from decimal import Decimal, InvalidOperation

from django.http import Http404
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.audit.services import jsonable
from apps.planning.models import FiscalYear
from apps.scoring import engine
from apps.scoring.types import ActivityInput

MAX_PREVIEW_ROWS = 5000


def _d(value) -> Decimal:
    try:
        return Decimal(str(value).replace(",", "")) if value not in (None, "") else Decimal(0)
    except InvalidOperation:
        return Decimal(0)


class PreviewView(APIView):
    """POST ``{"fiscal_year_id", "activities": [{key, measure_type, annual_target, total_cost,
    manual_weight, targets[12]}]}`` → weights per key, cumulative planned curve, funds total.
    Read-only: it stores nothing (allow-listed in the audit coverage test, D29)."""

    def post(self, request):
        fy = (
            FiscalYear.objects.select_related("profile").filter(pk=request.data.get("fiscal_year_id")).first()
            if (request.data.get("fiscal_year_id"))
            else None
        )
        if fy is None:
            raise Http404()
        items = request.data.get("activities") or []
        if not isinstance(items, list) or len(items) > MAX_PREVIEW_ROWS:
            return Response({"activities": ["Send a list of at most 5,000 activities."]}, status=400)
        activities = []
        for i, a in enumerate(items):
            targets = list(a.get("targets") or [])[:12]
            targets += [0] * (12 - len(targets))
            measure = a.get("measure_type") if a.get("measure_type") in engine.MEASURE_TYPES else "quantity"
            activities.append(
                ActivityInput(
                    id=str(a.get("key", i)),
                    measure_type=measure,
                    annual_target=_d(a.get("annual_target")),
                    total_cost=_d(a.get("total_cost")),
                    planned=tuple(_d(t) for t in targets),
                    manual_weight=_d(a.get("manual_weight"))
                    if a.get("manual_weight") not in (None, "")
                    else None,
                )
            )
        profile = fy.profile.to_engine()
        result = engine.plan_result(activities, [], profile)
        return Response(
            {
                "weighting": profile.weighting,
                "weights": {r.id: jsonable(r.weight) for r in result.activities},
                "cum_plan": [jsonable(v) for v in result.cum_plan],
                "funds_total": jsonable(result.funds_total),
            }
        )

from django.urls import path

from apps.planning import api, plan_api

urlpatterns = [
    path("fiscal-years", api.FiscalYearListView.as_view(), name="fiscal-years"),
    path("fiscal-years/<uuid:fy_id>", api.FiscalYearDetailView.as_view(), name="fiscal-year"),
    path("scoring-presets", api.PresetListView.as_view(), name="scoring-presets"),
    path("scoring-profiles/<uuid:profile_id>", api.ScoringProfileView.as_view(), name="scoring-profile"),
    path("plans", plan_api.PlanListView.as_view(), name="plans"),
    path("plans/<uuid:plan_id>", plan_api.PlanDetailView.as_view(), name="plan"),
    path("plans/<uuid:plan_id>/save", plan_api.PlanSaveView.as_view(), name="plan-save"),
    path("plans/<uuid:plan_id>/submit", plan_api.PlanSubmitView.as_view(), name="plan-submit"),
    path("plans/<uuid:plan_id>/approve", plan_api.PlanApproveView.as_view(), name="plan-approve"),
    path("plans/<uuid:plan_id>/return", plan_api.PlanReturnView.as_view(), name="plan-return"),
    path("plans/<uuid:plan_id>/revise", plan_api.PlanReviseView.as_view(), name="plan-revise"),
    path("plans/<uuid:plan_id>/versions", plan_api.PlanVersionsView.as_view(), name="plan-versions"),
    path("plans/<uuid:plan_id>/compare", plan_api.PlanCompareView.as_view(), name="plan-compare"),
    path("plans/<uuid:plan_id>/copy", plan_api.PlanCopyView.as_view(), name="plan-copy"),
]

from django.urls import path

from apps.structure import api

urlpatterns = [
    path("levels", api.LevelListView.as_view(), name="levels"),
    path("levels/<uuid:level_id>", api.LevelDetailView.as_view(), name="level"),
    path("offices", api.OfficeTreeView.as_view(), name="offices"),
    path("offices/import", api.OfficeImportView.as_view(), name="offices-import"),
    path("offices/reorder", api.OfficeReorderView.as_view(), name="offices-reorder"),
    path("offices/<uuid:office_id>", api.OfficeDetailView.as_view(), name="office"),
    path("offices/<uuid:office_id>/move", api.OfficeMoveView.as_view(), name="office-move"),
    path("groups", api.GroupListView.as_view(), name="groups"),
    path("groups/<uuid:group_id>", api.GroupDetailView.as_view(), name="group"),
    path("groups/<uuid:group_id>/members", api.GroupMembersView.as_view(), name="group-members"),
]

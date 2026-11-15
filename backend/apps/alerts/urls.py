from django.urls import path

from apps.alerts import api

urlpatterns = [
    path("alert-rules", api.AlertRuleView.as_view(), name="alert-rules"),
    path("notifications", api.NotificationListView.as_view(), name="notifications"),
    path("notifications/unread-count", api.UnreadCountView.as_view(), name="notifications-unread"),
    path("notifications/read-all", api.NotificationReadAllView.as_view(), name="notifications-read-all"),
    path(
        "notifications/<uuid:notification_id>/read",
        api.NotificationReadView.as_view(),
        name="notification-read",
    ),
]

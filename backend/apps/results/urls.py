from django.urls import path

from apps.results import api

urlpatterns = [path("results/preview", api.PreviewView.as_view(), name="results-preview")]

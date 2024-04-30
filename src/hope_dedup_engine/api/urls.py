from django.urls import path

from hope_dedup_engine.apps.facerecognize.views import InitiateDeduplication, RetrieveDeduplicationResults

app_name = "dedup-api"
urlpatterns = [
    path("dedupe/", InitiateDeduplication.as_view(), name="deduplicate"),
    path("dedupe/<uuid:task_id>/", RetrieveDeduplicationResults.as_view(), name="deduplication_results"),
]

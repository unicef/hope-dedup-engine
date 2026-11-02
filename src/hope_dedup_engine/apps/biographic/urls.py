from django.urls import include, path
from rest_framework import routers

from hope_dedup_engine.apps.biographic.views import BiographicDatasetViewSet, BiographicFindingsViewSet

datasets_router = routers.SimpleRouter()
datasets_router.register("datasets", BiographicDatasetViewSet, basename="biographic-datasets")

findings_router = routers.SimpleRouter()
findings_router.register("findings", BiographicFindingsViewSet, basename="biographic-findings")

PROGRAM_PREFIX = "api/biographic/<slug:business_area_slug>/<slug:program_code>/"

urlpatterns = [
    path(PROGRAM_PREFIX, include(datasets_router.urls)),
    path(f"{PROGRAM_PREFIX}datasets/<int:dataset_id>/", include(findings_router.urls)),
]

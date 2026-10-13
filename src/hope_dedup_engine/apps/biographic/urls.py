from django.urls import include, path
from rest_framework import routers

from hope_dedup_engine.apps.biographic.views import BiographicDatasetViewSet, BiographicPairsViewSet

datasets_router = routers.SimpleRouter()
datasets_router.register("datasets", BiographicDatasetViewSet, basename="biographic-datasets")

pairs_router = routers.SimpleRouter()
pairs_router.register("pairs", BiographicPairsViewSet, basename="biographic-pairs")

PROGRAM_PREFIX = "api/biographic/<slug:business_area_slug>/<slug:program_code>/"

urlpatterns = [
    path(PROGRAM_PREFIX, include(datasets_router.urls)),
    path(f"{PROGRAM_PREFIX}datasets/<int:dataset_id>/", include(pairs_router.urls)),
]

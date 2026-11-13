from django.urls import include, path, register_converter
from django.urls.converters import UUIDConverter
from rest_framework import routers

from hope_dedup_engine.apps.biographic.views import (
    BiographicDatasetViewSet,
    BiographicFindingsViewSet,
    BiographicGroupView,
    UUID_REGEX,
)


class AnyCaseUUIDConverter(UUIDConverter):
    regex = UUID_REGEX


register_converter(AnyCaseUUIDConverter, "anycase_uuid")

datasets_router = routers.SimpleRouter()
datasets_router.register("datasets", BiographicDatasetViewSet, basename="biographic-datasets")

findings_router = routers.SimpleRouter()
findings_router.register("findings", BiographicFindingsViewSet, basename="biographic-findings")

PROGRAM_PREFIX = "api/biographic/<slug:business_area_slug>/<slug:program_code>/"

urlpatterns = [
    path(PROGRAM_PREFIX, BiographicGroupView.as_view(), name="biographic-group"),
    path(PROGRAM_PREFIX, include(datasets_router.urls)),
    path(f"{PROGRAM_PREFIX}datasets/<anycase_uuid:dataset_id>/", include(findings_router.urls)),
]

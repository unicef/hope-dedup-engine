from django.urls import include, path

from drf_spectacular.views import (
    SpectacularAPIView,
    SpectacularRedocView,
    SpectacularSwaggerView,
)
from rest_framework import routers

from hope_dedup_engine.apps.api.views import (
    BulkEncodingViewSet,
    DeduplicationSetGroupView,
    DeduplicationSetViewSet,
    EncodingsExportViewSet,
    FindingsViewSet,
)

router = routers.SimpleRouter()
router.register("deduplication_sets", DeduplicationSetViewSet, basename="deduplication_sets")
router.register("deduplication_set_groups", DeduplicationSetGroupView, basename="deduplication_set_groups")
router.register("encodings_exports", EncodingsExportViewSet, basename="encodings_exports")

images_router = routers.SimpleRouter()
images_router.register("images", BulkEncodingViewSet, basename="images")

findings_router = routers.SimpleRouter()
findings_router.register("findings", FindingsViewSet, basename="findings")

urlpatterns = [
    path("", include(router.urls)),
    path(
        "deduplication_sets/<uuid:deduplication_set_pk>/",
        include(images_router.urls),
    ),
    path(
        "deduplication_sets/<uuid:deduplication_set_pk>/",
        include(findings_router.urls),
    ),
    path("api/rest/", SpectacularAPIView.as_view(), name="schema"),
    path(
        "api/rest/redoc/",
        SpectacularRedocView.as_view(url_name="schema"),
        name="redoc",
    ),
    path(
        "api/rest/swagger/",
        SpectacularSwaggerView.as_view(url_name="schema"),
        name="swagger-ui",
    ),
]

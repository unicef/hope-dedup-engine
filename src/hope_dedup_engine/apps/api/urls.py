from django.urls import include, path, re_path

from drf_spectacular.views import (
    SpectacularAPIView,
    SpectacularRedocView,
    SpectacularSwaggerView,
)
from rest_framework import routers
from rest_framework_nested import routers as nested_routers

from hope_dedup_engine.apps.api.const import (
    BULK_IMAGE_LIST,
    DEDUPLICATION_SET,
    DEDUPLICATION_SET_LIST,
    DUPLICATE_LIST,
    IGNORED_KEYS_LIST,
    IMAGE_LIST,
)
from hope_dedup_engine.apps.api.views import (
    BulkImageViewSet,
    DeduplicationSetViewSet,
    DuplicateViewSet,
    IgnoredKeyPairViewSet,
    ImageViewSet,
)

router = routers.SimpleRouter()
router.register(
    DEDUPLICATION_SET_LIST, DeduplicationSetViewSet, basename=DEDUPLICATION_SET_LIST
)

deduplication_sets_router = nested_routers.NestedSimpleRouter(
    router, DEDUPLICATION_SET_LIST, lookup=DEDUPLICATION_SET
)
deduplication_sets_router.register(IMAGE_LIST, ImageViewSet, basename=IMAGE_LIST)
deduplication_sets_router.register(
    BULK_IMAGE_LIST, BulkImageViewSet, basename=BULK_IMAGE_LIST
)
deduplication_sets_router.register(
    DUPLICATE_LIST, DuplicateViewSet, basename=DUPLICATE_LIST
)
deduplication_sets_router.register(
    IGNORED_KEYS_LIST, IgnoredKeyPairViewSet, basename=IGNORED_KEYS_LIST
)

urlpatterns = [
    path("", include(router.urls)),
    path("", include(deduplication_sets_router.urls)),
    path("api/rest/", SpectacularAPIView.as_view(), name="schema"),
    re_path(
        "^api/rest/swagger/$",
        SpectacularSwaggerView.as_view(url_name="schema"),
        name="swagger-ui",
    ),
    re_path(
        "^api/rest/redoc/$",
        SpectacularRedocView.as_view(url_name="schema"),
        name="redoc",
    ),
]

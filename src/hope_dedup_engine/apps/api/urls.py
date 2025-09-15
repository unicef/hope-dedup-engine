from django.urls import include, path

from drf_spectacular.views import (
    SpectacularAPIView,
    SpectacularRedocView,
    SpectacularSwaggerView,
)
from rest_framework.routers import DefaultRouter
from rest_framework_nested import routers as nested_routers

from hope_dedup_engine.apps.api.const import (
    BULK_IMAGE_LIST,
    DEDUPLICATION_SET,
    DEDUPLICATION_SET_LIST,
    DUPLICATE_LIST,
    IGNORED_FILENAME_LIST,
    IGNORED_REFERENCE_PK_LIST,
    IMAGE_LIST,
)
from hope_dedup_engine.apps.api.views import (
    BulkImageViewSet,
    DeduplicationSetViewSet,
    DuplicateViewSet,
    IgnoredFilenamePairViewSet,
    IgnoredReferencePkPairViewSet,
    ImageViewSet,
)

router = DefaultRouter()
router.register(DEDUPLICATION_SET_LIST.replace("_", "-"), DeduplicationSetViewSet, basename=DEDUPLICATION_SET_LIST)

deduplication_sets_router = nested_routers.NestedSimpleRouter(
    router, DEDUPLICATION_SET_LIST.replace("_", "-"), lookup=DEDUPLICATION_SET
)
deduplication_sets_router.register(IMAGE_LIST, ImageViewSet, basename=IMAGE_LIST)
deduplication_sets_router.register(BULK_IMAGE_LIST.replace("_", "-"), BulkImageViewSet, basename=BULK_IMAGE_LIST)
deduplication_sets_router.register(DUPLICATE_LIST, DuplicateViewSet, basename=DUPLICATE_LIST)
deduplication_sets_router.register(IGNORED_FILENAME_LIST, IgnoredFilenamePairViewSet, basename=IGNORED_FILENAME_LIST)
deduplication_sets_router.register(
    IGNORED_REFERENCE_PK_LIST.replace("_", "-"),
    IgnoredReferencePkPairViewSet,
    basename=IGNORED_REFERENCE_PK_LIST,
)

urlpatterns = [
    path("", include(router.urls)),
    path("", include(deduplication_sets_router.urls)),
    path("rest/", SpectacularAPIView.as_view(), name="schema"),
    path(
        "rest/swagger/",
        SpectacularSwaggerView.as_view(url_name="schema"),
        name="swagger-ui",
    ),
    path(
        "rest/redoc/",
        SpectacularRedocView.as_view(url_name="schema"),
        name="redoc",
    ),
]

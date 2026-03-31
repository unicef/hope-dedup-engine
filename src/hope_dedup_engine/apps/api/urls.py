from django.urls import include, path

from drf_spectacular.views import (
    SpectacularAPIView,
    SpectacularRedocView,
    SpectacularSwaggerView,
)
from rest_framework import routers
from rest_framework_nested import routers as nested_routers

from hope_dedup_engine.apps.api.const import (
    BULK_ENCODING_LIST,
    DEDUPLICATION_SET,
    DEDUPLICATION_SET_LIST,
    DUPLICATE_LIST,
    ENCODING_LIST,
)
from hope_dedup_engine.apps.api.views import (
    BulkEncodingViewSet,
    DeduplicationSetGroupConfigView,
    DeduplicationSetViewSet,
    DuplicateViewSet,
    EncodingViewSet,
)

router = routers.SimpleRouter()
router.register(DEDUPLICATION_SET_LIST, DeduplicationSetViewSet, basename=DEDUPLICATION_SET_LIST)

deduplication_sets_router = nested_routers.NestedSimpleRouter(router, DEDUPLICATION_SET_LIST, lookup=DEDUPLICATION_SET)
deduplication_sets_router.register(ENCODING_LIST, EncodingViewSet, basename=ENCODING_LIST)
deduplication_sets_router.register(BULK_ENCODING_LIST, BulkEncodingViewSet, basename=BULK_ENCODING_LIST)
deduplication_sets_router.register(DUPLICATE_LIST, DuplicateViewSet, basename=DUPLICATE_LIST)

group_config_view = DeduplicationSetGroupConfigView.as_view({"get": "retrieve", "post": "update"})

urlpatterns = [
    path("", include(router.urls)),
    path("", include(deduplication_sets_router.urls)),
    path(
        "deduplication_set_groups/config/<str:reference_pk>/",
        group_config_view,
        name="deduplication_set_group_config",
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

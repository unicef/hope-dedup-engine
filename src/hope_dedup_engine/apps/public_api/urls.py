from django.urls import include, path

from rest_framework import routers
from rest_framework_nested import routers as nested_routers

from hope_dedup_engine.apps.public_api.const import (
    BULK_IMAGE_LIST,
    DEDUPLICATION_SET,
    DEDUPLICATION_SET_LIST,
    IMAGE_LIST,
)
from hope_dedup_engine.apps.public_api.views import BulkImageViewSet, DeduplicationSetViewSet, ImageViewSet

router = routers.SimpleRouter()
router.register(DEDUPLICATION_SET_LIST, DeduplicationSetViewSet, basename=DEDUPLICATION_SET_LIST)

deduplication_sets_router = nested_routers.NestedSimpleRouter(router, DEDUPLICATION_SET_LIST, lookup=DEDUPLICATION_SET)
deduplication_sets_router.register(IMAGE_LIST, ImageViewSet, basename=IMAGE_LIST)
deduplication_sets_router.register(BULK_IMAGE_LIST, BulkImageViewSet, basename=BULK_IMAGE_LIST)

urlpatterns = [path("", include(router.urls)), path("", include(deduplication_sets_router.urls))]

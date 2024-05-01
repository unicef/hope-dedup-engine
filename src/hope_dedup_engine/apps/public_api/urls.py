from rest_framework import routers

from hope_dedup_engine.apps.public_api.views import DeduplicationSetViewSet

DEDUPLICATION_SET = "deduplication_set"

router = routers.SimpleRouter()
router.register(f"{DEDUPLICATION_SET}s", DeduplicationSetViewSet, basename=DEDUPLICATION_SET)
urlpatterns = router.urls

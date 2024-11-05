from django.db import models

from constance import config
from django_celery_boost.models import CeleryTaskModel

from hope_dedup_engine.apps.api.deduplication.lock import DeduplicationSetLock
from hope_dedup_engine.apps.api.models import DeduplicationSet


class DedupJob(CeleryTaskModel):
    deduplication_set = models.ForeignKey(
        "DeduplicationSet", on_delete=models.CASCADE, related_name="jobs"
    )
    serialized_lock = models.CharField(max_length=128, null=True, editable=False)
    progress = models.IntegerField(default=0)

    celery_task_name = (
        "hope_dedup_engine.apps.api.deduplication.process.find_duplicates"
    )

    def acquire_lock(self) -> None:
        if config.DEDUPLICATION_SET_LOCK_ENABLED:
            self.serialized_lock = str(
                DeduplicationSetLock.for_deduplication_set(self.deduplication_set)
            )
            self.save()

    def queue(self, use_version: bool = True) -> str | None:
        self.acquire_lock()

        self.deduplication_set.state = DeduplicationSet.State.PROCESSING
        self.deduplication_set.save()

        return super().queue(use_version=use_version)

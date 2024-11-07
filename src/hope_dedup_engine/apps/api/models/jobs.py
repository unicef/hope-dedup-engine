from django.db import models

from django_celery_boost.models import CeleryTaskModel


class DedupJob(CeleryTaskModel):
    deduplication_set = models.OneToOneField(
        "DeduplicationSet", on_delete=models.CASCADE
    )
    serialized_lock = models.CharField(max_length=128, null=True, editable=False)
    progress = models.IntegerField(default=0)

    celery_task_name = (
        "hope_dedup_engine.apps.api.deduplication.process.find_duplicates"
    )

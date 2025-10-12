from django.db import models

from django_celery_boost.models import CeleryTaskModel


class DedupJob(CeleryTaskModel):
    deduplication_set = models.ForeignKey(
        "DeduplicationSet",
        on_delete=models.CASCADE,
        related_name="dedup_jobs",
    )
    progress = models.IntegerField(default=0)

    celery_task_name = "hope_dedup_engine.apps.api.deduplication.process.find_duplicates"

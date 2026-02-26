from django.db import models

from django_celery_boost.models import CeleryTaskModel


class DedupJob(CeleryTaskModel):
    deduplication_set = models.ForeignKey(
        "DeduplicationSet",
        on_delete=models.CASCADE,
        related_name="dedup_jobs",
    )

    celery_task_name = "hope_dedup_engine.apps.api.celery_tasks.not_a_task"


class MainJob(DedupJob):
    encode_only = models.BooleanField(default=False)

    celery_task_name = "hope_dedup_engine.apps.api.deduplication.process.find_duplicates"


class SyncDnnFilesJob(CeleryTaskModel):
    force = models.BooleanField(
        default=False, help_text="If True, forces the re-download of files even if they already exist locally"
    )

    celery_task_name = "hope_dedup_engine.apps.faces.celery_tasks.sync_dnn_files"

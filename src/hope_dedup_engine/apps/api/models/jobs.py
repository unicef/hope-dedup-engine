from django.contrib.postgres.fields import ArrayField
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


class EncodeChunkJob(DedupJob):
    encoding_ids = ArrayField(models.UUIDField(), help_text="Encoding IDs to encode")

    celery_task_name = "hope_dedup_engine.apps.faces.celery_tasks.encode_chunk"


class DedupeChunkJob(DedupJob):
    encoding_ids0 = ArrayField(models.UUIDField(), help_text="First batch of encoding IDs to encode")
    encoding_ids1 = ArrayField(models.UUIDField(), help_text="Second batch of encoding IDs to encode")

    celery_task_name = "hope_dedup_engine.apps.faces.celery_tasks.dedupe_chunk"


class CallbackFindingsJob(DedupJob):
    celery_task_name = "hope_dedup_engine.apps.faces.celery_tasks.callback_findings"


class DeduplicateDatasetJob(DedupJob):
    celery_task_name = "hope_dedup_engine.apps.faces.celery_tasks.deduplicate_dataset"


class SyncDnnFilesJob(CeleryTaskModel):
    force = models.BooleanField(
        default=False, help_text="If True, forces the re-download of files even if they already exist locally"
    )

    celery_task_name = "hope_dedup_engine.apps.faces.celery_tasks.sync_dnn_files"

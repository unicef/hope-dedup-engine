from django.db import models

from django_celery_boost.models import CeleryTaskModel


class GracefulJobCancellationError(Exception):
    """Raised when a running job cooperatively stops after cancellation was requested."""

    def __init__(self, *args: object, processed: int | None = None) -> None:
        super().__init__(*args)
        self.processed = processed


class DedupJob(CeleryTaskModel):
    deduplication_set = models.ForeignKey(
        "DeduplicationSet",
        on_delete=models.CASCADE,
        related_name="dedup_jobs",
    )

    celery_task_name = "hope_dedup_engine.apps.api.celery_tasks.not_a_task"

    def ensure_not_cancelled(self) -> None:
        if self.is_termination_requested:
            raise GracefulJobCancellationError(f"Cancellation requested for job #{self.pk}")


class MainJob(DedupJob):
    encode_only = models.BooleanField(default=False)

    celery_task_name = "hope_dedup_engine.apps.api.deduplication.process.find_duplicates"


class SyncDnnFilesJob(CeleryTaskModel):
    force = models.BooleanField(
        default=False, help_text="If True, forces the re-download of files even if they already exist locally"
    )

    celery_task_name = "hope_dedup_engine.apps.faces.celery_tasks.sync_dnn_files"

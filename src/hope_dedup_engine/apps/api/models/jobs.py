from django.db import models

from django_celery_boost.models import CeleryTaskModel


class DedupJob(CeleryTaskModel):
    deduplication_set = models.ForeignKey(
        "DeduplicationSet",
        on_delete=models.CASCADE,
        related_name="dedup_jobs",
    )
    serialized_lock = models.CharField(max_length=128, null=True, editable=False)
    progress = models.IntegerField(default=0)
    files_data = models.JSONField(null=True, editable=False)

    celery_task_name = "hope_dedup_engine.apps.api.deduplication.process.find_duplicates"

    def get_filenames(self) -> list[str]:
        if not self.files_data:
            return []

        return [f.get("filename") for f in self.files_data]

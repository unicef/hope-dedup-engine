from django_celery_boost.models import CeleryTaskModel


class DedupJob(CeleryTaskModel):
    celery_task_name = (
        "hope_dedup_engine.apps.api.deduplication.process.find_duplicates"
    )

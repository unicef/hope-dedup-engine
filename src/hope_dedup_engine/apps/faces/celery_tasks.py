from celery import shared_task

from hope_dedup_engine.apps.faces.utils.celery_utils import task_lifecycle
from hope_dedup_engine.apps.faces.utils.duplication_detector import DuplicationDetector


@shared_task(bind=True, soft_time_limit=0.5 * 60 * 60, time_limit=1 * 60 * 60)
@task_lifecycle(name="Deduplicate", ttl=1 * 60 * 60)
# TODO: Use DeduplicationSet objects as input to deduplication pipeline
def deduplicate(self, filename: str):
    # deduplicate.delay(filename=filename)
    dd = DuplicationDetector(filename)
    return dd.find_duplicates()

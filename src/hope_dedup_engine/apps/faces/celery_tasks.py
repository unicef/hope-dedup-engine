from uuid import UUID

from celery import shared_task

from hope_dedup_engine.apps.faces.utils.celery_utils import task_lifecycle
from hope_dedup_engine.apps.faces.utils.duplication_detector import DuplicationDetector
from hope_dedup_engine.apps.public_api.models import DeduplicationSet


@shared_task(bind=True, soft_time_limit=0.5 * 60 * 60, time_limit=1 * 60 * 60)
@task_lifecycle(name="Deduplicate", ttl=1 * 60 * 60)
def deduplicate(self, pk: UUID) -> set[str]:
    duplicates = set()
    for filename in DeduplicationSet.objects.get(pk=pk).image_set.values_list("filename", flat=True):
        dd = DuplicationDetector(filename)
        duplicates.update(dd.detect_duplicates())
    return duplicates

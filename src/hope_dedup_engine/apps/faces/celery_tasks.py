from celery import chain, shared_task

from hope_dedup_engine.apps.faces.utils.celery_utils import task_lifecycle
from hope_dedup_engine.apps.faces.utils.duplication_detector import DuplicationDetector


@shared_task(bind=True)
@task_lifecycle(name="Face Encodings")
def encode_faces(self, filename: str):
    dd = DuplicationDetector(filename)
    return dd.encode_faces()


@shared_task(bind=True)
@task_lifecycle(name="Deduplicate")
def deduplicate(self, filename: str):
    dd = DuplicationDetector(filename)
    return dd.find_duplicates()


# TODO: Use DeduplicationSet objects as input to deduplication_pipeline
def deduplication_pipeline(filename: str):
    dd = DuplicationDetector(filename)
    if dd.has_encodings:
        return deduplicate.delay(filename)
    else:
        return chain(encode_faces.si(filename), deduplicate.si(filename))()

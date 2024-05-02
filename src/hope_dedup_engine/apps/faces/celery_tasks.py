from celery import shared_task

from hope_dedup_engine.apps.faces.utils.celery_utils import task_lifecycle
from hope_dedup_engine.apps.faces.utils.duplication_detector import DuplicationDetector


@shared_task(bind=True)
@task_lifecycle(name="Face Encodings")
def encode_faces(self, dd: DuplicationDetector):
    return dd.encode_faces()


@shared_task(bind=True)
@task_lifecycle(name="Deduplicate")
def deduplicate(self, dd: DuplicationDetector):
    return dd.find_duplicates()


# TODO: Use DeduplicationSet objects as input to deduplication_pipeline
def deduplication_pipeline(image_path: str):
    dd: DuplicationDetector = DuplicationDetector(image_path)
    # TODO: use chain(encode_faces.s(dd), deduplicate.s(dd))() if not dd.has_encodings
    return encode_faces.s(dd)()

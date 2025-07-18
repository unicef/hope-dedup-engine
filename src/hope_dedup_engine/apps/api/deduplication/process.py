from dataclasses import asdict

from django.db.models import F

import sentry_sdk
from celery import chord, shared_task

from hope_dedup_engine.apps.api.deduplication.config import DeduplicationSetConfig

from hope_dedup_engine.apps.api.models import DedupJob, DeduplicationSet, Finding
from hope_dedup_engine.apps.api.utils.notification import send_notification

from hope_dedup_engine.apps.faces.celery_tasks import (
    callback_encodings,
    encode_chunk,
    get_chunks,
    handle_error,
)

HOUR = 60 * 60


def update_job_progress(job: DedupJob, progress: int) -> None:
    job.progress = progress
    job.save(update_fields=["progress"])


@shared_task(soft_time_limit=0.5 * HOUR, time_limit=1 * HOUR)
def find_duplicates(dedup_job_id: int, version: int) -> None:
    dedup_job: DedupJob = DedupJob.objects.get(pk=dedup_job_id, version=version)
    deduplication_set = dedup_job.deduplication_set
    try:
        deduplication_set.state = DeduplicationSet.State.DIRTY
        deduplication_set.save(update_fields=["state"])
        send_notification(deduplication_set.notification_url)

        config = asdict(DeduplicationSetConfig.from_deduplication_set(deduplication_set))

        # clean results
        Finding.objects.filter(deduplication_set=deduplication_set).delete()
        dedup_job.progress = 0
        dedup_job.save(update_fields=["progress"])

        weight_total = 1
        deduplication_set.finding_set.update(score=F("score") / weight_total)

        files = deduplication_set.image_set.values_list("filename", flat=True)
        chunks = get_chunks(files)
        tasks = [encode_chunk.s(chunk, config) for chunk in chunks]
        chord_id = chord(tasks)(callback_encodings.s(config=config))

        return {
            "deduplication_set": str(deduplication_set),
            "chord_id": str(chord_id),
            "chunks": len(chunks),
        }
    except Exception as e:
        handle_error(deduplication_set)
        sentry_sdk.capture_exception(e)
        raise

from dataclasses import asdict
from typing import Any

import sentry_sdk
from celery import chord, shared_task

from hope_dedup_engine.apps.api.deduplication.config import DeduplicationSetConfig

from hope_dedup_engine.apps.api.models import DedupJob, DeduplicationSet, Finding
from hope_dedup_engine.apps.api.utils.notification import send_notification

from hope_dedup_engine.apps.faces.celery_tasks import (
    encode_chunk,
    find_duplicates_in_set,
    get_chunks,
    finish_with_error,
)

HOUR = 60 * 60


@shared_task(soft_time_limit=0.5 * HOUR, time_limit=1 * HOUR)
def find_duplicates(dedup_job_id: int, version: int) -> dict[str, Any]:
    dedup_job: DedupJob = DedupJob.objects.get(pk=dedup_job_id, version=version)
    deduplication_set = dedup_job.deduplication_set
    try:
        deduplication_set.set_state(DeduplicationSet.State.PROCESSING)
        send_notification(deduplication_set.notification_url)

        config = asdict(DeduplicationSetConfig.from_deduplication_set(deduplication_set))

        # clean results
        Finding.objects.filter(deduplication_set=deduplication_set).delete()
        dedup_job.progress = 0
        dedup_job.save(update_fields=["progress"])

        files = deduplication_set.image_set.values_list("filename", flat=True)
        chunks = get_chunks(files)
        tasks = [encode_chunk.s(chunk, config, str(deduplication_set.pk)) for chunk in chunks]
        chord_id = chord(tasks)(find_duplicates_in_set.s(config=config, deduplication_set_id=str(deduplication_set.pk)))

        return {
            "deduplication_set": str(deduplication_set),
            "chord_id": str(chord_id),
            "chunks": len(chunks),
        }
    except Exception as e:
        finish_with_error(deduplication_set, e)
        sentry_sdk.capture_exception(e)
        raise

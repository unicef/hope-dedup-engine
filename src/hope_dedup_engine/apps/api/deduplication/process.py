from datetime import timedelta
from typing import Any

from django.db import transaction
from django.utils import timezone

import sentry_sdk
from celery import chord, shared_task, group

from hope_dedup_engine.apps.api.models import MainJob, DeduplicationSet
from hope_dedup_engine.apps.api.models.deduplication import DeduplicationSetGroup
from hope_dedup_engine.apps.api.models.jobs import EncodeChunkJob, DeduplicateDatasetJob
from hope_dedup_engine.apps.api.utils.notification import send_notification

from hope_dedup_engine.apps.faces.celery_tasks import (
    get_chunks,
    finish_with_error,
    finish_with_success,
    ChunkPurpose,
)

HOUR = 60 * 60
RESCHEDULE_INTERVAL = 6 * HOUR
STALE_PROCESSING_THRESHOLD = 24 * HOUR


def try_acquire_processing_lock(deduplication_set: DeduplicationSet) -> DeduplicationSet | None:
    with transaction.atomic():
        DeduplicationSetGroup.objects.select_for_update().get(pk=deduplication_set.group_id)

        if deduplication_set.state == DeduplicationSet.State.PROCESSING:
            time_since_update = timezone.now() - deduplication_set.updated_at

            if time_since_update > timedelta(seconds=STALE_PROCESSING_THRESHOLD):
                sentry_sdk.capture_message(
                    f"Stale PROCESSING state detected for {deduplication_set}. "
                    f"Last updated {time_since_update} ago. Proceeding with new processing.",
                    level="warning",
                )
            else:
                return None

        deduplication_set.set_state(DeduplicationSet.State.PROCESSING)
        return deduplication_set


@shared_task(bind=True, soft_time_limit=0.5 * HOUR, time_limit=1 * HOUR)
def find_duplicates(self, dedup_job_id: int, version: int) -> dict[str, Any]:
    main_job: MainJob = MainJob.objects.get(pk=dedup_job_id, version=version)

    deduplication_set = try_acquire_processing_lock(main_job.deduplication_set)

    if deduplication_set is None:
        self.apply_async(
            args=[dedup_job_id, version],
            countdown=RESCHEDULE_INTERVAL,
        )
        return {
            "status": "rescheduled",
            "reason": "dataset already being processed",
            "retry_in_seconds": RESCHEDULE_INTERVAL,
        }

    try:
        send_notification(deduplication_set)

        encoding_ids = deduplication_set.encodings_without_embeddings().values_list("id", flat=True)
        chunks = get_chunks(encoding_ids, purpose=ChunkPurpose.ENCODE)
        tasks = [
            EncodeChunkJob.objects.create(deduplication_set=deduplication_set, encoding_ids=chunk).s()
            for chunk in chunks
        ]
        if main_job.encode_only:
            chord_id = group(tasks)()
            finish_with_success(deduplication_set)
        else:
            chord_id = chord(tasks)(DeduplicateDatasetJob.objects.create(deduplication_set_id=deduplication_set.pk).s())

        return {
            "deduplication_set": str(deduplication_set),
            "chord_id": str(chord_id),
            "chunks": len(chunks),
        }
    except Exception as e:
        finish_with_error(deduplication_set, e)
        sentry_sdk.capture_exception(e)
        raise

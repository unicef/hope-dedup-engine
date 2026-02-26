from datetime import timedelta
from typing import Any

from django.db import transaction
from django.utils import timezone

import sentry_sdk
from celery import shared_task

from hope_dedup_engine.apps.api.deduplication.config import DeduplicationSetConfig
from hope_dedup_engine.apps.api.models import MainJob, DeduplicationSet
from hope_dedup_engine.apps.api.models.deduplication import DeduplicationSetGroup
from hope_dedup_engine.apps.api.utils.notification import send_notification
from hope_dedup_engine.apps.faces.services.facial import dedupe_all, encode_faces

HOUR = 60 * 60
RESCHEDULE_INTERVAL = 6 * HOUR
STALE_PROCESSING_THRESHOLD = 24 * HOUR


def finish_processing(ds: DeduplicationSet, error: Exception | None = None) -> None:
    if error:
        ds.set_state(DeduplicationSet.State.FAILED, error)
    else:
        ds.set_state(DeduplicationSet.State.READY)
    send_notification(ds)


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
    """
    Process a deduplication job: encode faces and find duplicates.

    This task handles the complete deduplication workflow:
    1. Acquires a processing lock on the deduplication set
    2. Encodes all images without embeddings
    3. Runs deduplication (unless encode_only is True)
    4. Updates state and sends notification
    """
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
        config = DeduplicationSetConfig.from_deduplication_set(deduplication_set)

        # Encode all images without embeddings
        encoding_ids = list(deduplication_set.encodings_without_embeddings().values_list("id", flat=True))
        encodings_count = len(encoding_ids)

        if encoding_ids:
            encode_faces(
                deduplication_set,
                encoding_ids,
                config.face_confidence_threshold,
                config.face_coverage_threshold,
                config.deduplicate.model_name,
                config.deduplicate.detector_backend,
                align=config.deduplicate.align,
            )

        # Run deduplication unless encode_only
        findings_count = 0
        if not main_job.encode_only:
            findings_count = dedupe_all(
                deduplication_set=deduplication_set,
                duplicate_confidence_threshold=config.duplicate_confidence_threshold,
                model_name=config.deduplicate.model_name,
                distance_metric=config.deduplicate.distance_metric,
            )

        finish_processing(deduplication_set)

        return {
            "deduplication_set": str(deduplication_set),
            "encodings_processed": encodings_count,
            "findings_created": findings_count,
        }
    except Exception as e:
        finish_processing(deduplication_set, e)
        sentry_sdk.capture_exception(e)
        raise

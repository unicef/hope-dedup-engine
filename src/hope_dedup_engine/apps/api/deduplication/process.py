import traceback
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


def _append_log(  # noqa
    ds: DeduplicationSet,
    config: DeduplicationSetConfig | None,
    job: MainJob,
    encodings_count: int = 0,
    findings_count: int = 0,
    error: Exception | None = None,
) -> None:
    entry: dict[str, Any] = {
        "timestamp": timezone.now().isoformat(),
        "action": "encode" if job.encode_only else "deduplicate",
        "state": ds.get_state_display(),
        "config": config.as_dict() if config else None,
        "encodings_processed": encodings_count,
        "findings_created": findings_count,
    }
    if error:
        entry["error"] = "".join(traceback.format_exception(error))

    if not isinstance(ds.log, list):
        ds.log = []
    ds.log.append(entry)
    ds.save(update_fields=["log"])


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


@shared_task(bind=True)
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

    config = None
    try:
        send_notification(deduplication_set)
        config = DeduplicationSetConfig.from_deduplication_set(deduplication_set)

        encoding_ids = list(deduplication_set.encodings_without_embeddings().values_list("id", flat=True))
        encodings_count = len(encoding_ids)

        if encoding_ids:
            encode_faces(
                deduplication_set,
                encoding_ids,
                config,
            )

        findings_count = 0
        if not main_job.encode_only:
            findings_count = dedupe_all(deduplication_set, config)

        finish_processing(deduplication_set)

        _append_log(deduplication_set, config, main_job, encodings_count, findings_count)

        return {
            "deduplication_set": str(deduplication_set),
            "encodings_processed": encodings_count,
            "findings_created": findings_count,
        }
    except Exception as e:
        finish_processing(deduplication_set, e)
        _append_log(deduplication_set, config, main_job, error=e)
        sentry_sdk.capture_exception(e)
        raise

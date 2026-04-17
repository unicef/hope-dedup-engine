import traceback
from typing import Any

from django.utils import timezone

import sentry_sdk
from celery import shared_task

from hope_dedup_engine.apps.api.deduplication.config import DeduplicationSetConfig
from hope_dedup_engine.apps.api.models import MainJob, DeduplicationSet
from hope_dedup_engine.apps.api.utils.notification import send_notification
from hope_dedup_engine.apps.faces.services.facial import dedupe_all, encode_faces


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

    ds.log.append(entry)
    ds.save(update_fields=["log"])


@shared_task(bind=True)
def find_duplicates(self, dedup_job_id: int, version: int) -> dict[str, Any]:
    """
    Process a deduplication job: encode faces and find duplicates.

    State transitions:
        ENCODING_IN_PROGRESS -> ENCODED -> DEDUPLICATION_IN_PROGRESS -> DEDUPLICATED
    On failure:
        ENCODING_IN_PROGRESS -> ENCODING_FAILED
        DEDUPLICATION_IN_PROGRESS -> DEDUPLICATION_FAILED

    The processing lock on the group is acquired by the caller (view/admin)
    before queuing the task and released here in a finally block.
    """
    main_job: MainJob = MainJob.objects.get(pk=dedup_job_id, version=version)
    deduplication_set = main_job.deduplication_set
    group = deduplication_set.group

    config = None
    encodings_count = 0
    findings_count = 0
    try:
        send_notification(deduplication_set)
        config = DeduplicationSetConfig.from_deduplication_set(deduplication_set)

        encoding_ids = list(deduplication_set.encodings_without_embeddings().values_list("id", flat=True))
        encodings_count = len(encoding_ids)

        if encoding_ids:
            encode_faces(deduplication_set, encoding_ids, config)

        deduplication_set.set_state(DeduplicationSet.State.ENCODED)
        send_notification(deduplication_set)

        if not main_job.encode_only:
            deduplication_set.set_state(DeduplicationSet.State.DEDUPLICATION_IN_PROGRESS)
            send_notification(deduplication_set)

            findings_count = dedupe_all(deduplication_set, config)

            deduplication_set.set_state(DeduplicationSet.State.DEDUPLICATED)
            send_notification(deduplication_set)

        _append_log(deduplication_set, config, main_job, encodings_count, findings_count)

        return {
            "deduplication_set": str(deduplication_set),
            "encodings_processed": encodings_count,
            "findings_created": findings_count,
        }
    except Exception as e:
        if deduplication_set.state == DeduplicationSet.State.DEDUPLICATION_IN_PROGRESS:
            deduplication_set.set_state(DeduplicationSet.State.DEDUPLICATION_FAILED, e)
        else:
            deduplication_set.set_state(DeduplicationSet.State.ENCODING_FAILED, e)
        send_notification(deduplication_set)
        _append_log(deduplication_set, config, main_job, encodings_count, findings_count, error=e)
        sentry_sdk.capture_exception(e)
        raise
    finally:
        group.release_processing_lock()

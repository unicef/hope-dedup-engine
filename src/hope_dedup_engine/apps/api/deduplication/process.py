import logging
import traceback
from typing import Any

from django.utils import timezone

import sentry_sdk
from celery import shared_task, states
from celery.exceptions import Ignore

from hope_dedup_engine.apps.api.deduplication.config import DeduplicationSetConfig
from hope_dedup_engine.apps.api.models import MainJob, DeduplicationSet
from hope_dedup_engine.apps.api.models.jobs import GracefulJobCancellationError
from hope_dedup_engine.apps.api.utils.notification import (
    RESULT_SENT,
    ErrorMessage,
    WarningMessage,
    send_notification,
)
from hope_dedup_engine.apps.faces.services.facial import dedupe_all, encode_faces

logger = logging.getLogger(__name__)

_CANCELLED_STATES = {
    DeduplicationSet.State.ENCODING_IN_PROGRESS: DeduplicationSet.State.ENCODING_FAILED,
    DeduplicationSet.State.DEDUPLICATION_IN_PROGRESS: DeduplicationSet.State.DEDUPLICATION_FAILED,
}


def _append_log(  # noqa
    ds: DeduplicationSet,
    config: DeduplicationSetConfig | None,
    job: MainJob,
    encodings_count: int = 0,
    findings_count: int = 0,
    notifications: list[dict[str, str]] | None = None,
    error: Exception | None = None,
) -> None:
    entry: dict[str, Any] = {
        "timestamp": timezone.now().isoformat(),
        "action": "encode" if job.encode_only else "deduplicate",
        "state": ds.get_state_display(),
        "config": config.as_dict() if config else None,
        "encodings_processed": encodings_count,
        "findings_created": findings_count,
        "notifications": notifications or [],
    }
    if error:
        entry["error"] = "".join(traceback.format_exception(error))

    ds.log.append(entry)
    ds.save(update_fields=["log"])


def _notify(ds: DeduplicationSet, outcomes: list[dict[str, str]]) -> None:
    """Notify HOPE about the current state and record whether it went through.

    `send_notification` reports a skip (no url, notifications disabled) or a delivery
    failure through its return value, which would otherwise be lost.
    """
    result = send_notification(ds)
    if isinstance(result, ErrorMessage):
        logger.error("Notification failed for deduplication set %s: %s", ds.pk, result)
    elif isinstance(result, WarningMessage):
        logger.warning("Notification skipped for deduplication set %s: %s", ds.pk, result)

    outcomes.append(
        {
            "state": ds.get_state_display(),
            "result": result if isinstance(result, str) else RESULT_SENT,
        }
    )


def _apply_cancelled_state(ds: DeduplicationSet, error: Exception) -> None:
    failed_state = _CANCELLED_STATES.get(ds.state)
    if failed_state is not None:
        ds.set_state(failed_state, error)


def _revoke_cancelled_task(task: Any, job: MainJob, error: GracefulJobCancellationError) -> None:
    job.cancel()
    task.update_state(
        state=states.REVOKED,
        meta={
            "exc_type": type(error).__name__,
            "exc_module": type(error).__module__,
            "exc_message": str(error),
        },
    )


@shared_task(bind=True)
def find_duplicates(self, dedup_job_id: int, version: int) -> dict[str, Any]:
    """
    Process a deduplication job: encode faces and find duplicates.

    State transitions:
        ENCODING_IN_PROGRESS -> ENCODED -> DEDUPLICATION_IN_PROGRESS -> DEDUPLICATED
    On failure:
        ENCODING_IN_PROGRESS -> ENCODING_FAILED
        DEDUPLICATION_IN_PROGRESS -> DEDUPLICATION_FAILED
    On graceful cancellation:
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
    notifications: list[dict[str, str]] = []
    try:
        main_job.ensure_not_cancelled()
        _notify(deduplication_set, notifications)
        config = DeduplicationSetConfig.from_deduplication_set(deduplication_set)

        encoding_ids = list(deduplication_set.encodings_without_embeddings().values_list("id", flat=True))
        encodings_count = 0
        if encoding_ids:
            encodings_count = encode_faces(deduplication_set, encoding_ids, config, job=main_job)

        main_job.ensure_not_cancelled()
        deduplication_set.set_state(DeduplicationSet.State.ENCODED)
        _notify(deduplication_set, notifications)

        if not main_job.encode_only:
            deduplication_set.set_state(DeduplicationSet.State.DEDUPLICATION_IN_PROGRESS)
            _notify(deduplication_set, notifications)

            findings_count = dedupe_all(deduplication_set, config, job=main_job)

            deduplication_set.set_state(DeduplicationSet.State.DEDUPLICATED)
            _notify(deduplication_set, notifications)

        _append_log(deduplication_set, config, main_job, encodings_count, findings_count, notifications)

        return {
            "deduplication_set": str(deduplication_set),
            "encodings_processed": encodings_count,
            "findings_created": findings_count,
        }
    except GracefulJobCancellationError as e:
        logger.info("Task cancelled gracefully for MainJob #%s", main_job.pk)
        if e.processed is not None:
            encodings_count = e.processed
        _apply_cancelled_state(deduplication_set, e)
        _notify(deduplication_set, notifications)
        _append_log(deduplication_set, config, main_job, encodings_count, findings_count, notifications, error=e)
        _revoke_cancelled_task(self, main_job, e)
        raise Ignore from e
    except Exception as e:
        if deduplication_set.state == DeduplicationSet.State.DEDUPLICATION_IN_PROGRESS:
            deduplication_set.set_state(DeduplicationSet.State.DEDUPLICATION_FAILED, e)
        else:
            deduplication_set.set_state(DeduplicationSet.State.ENCODING_FAILED, e)
        _notify(deduplication_set, notifications)
        _append_log(deduplication_set, config, main_job, encodings_count, findings_count, notifications, error=e)
        sentry_sdk.capture_exception(e)
        raise
    finally:
        group.release_processing_lock()

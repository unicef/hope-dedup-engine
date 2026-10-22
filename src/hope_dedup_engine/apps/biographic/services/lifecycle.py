"""The lifecycle steps a client can request on a set.

Each function owns its checks, the state transition, any rollback, and the task
it queues. They raise `LifecycleConflictError` instead of returning an HTTP status, so
the same rules hold whether the caller is a view, the admin, or a test.
"""

import logging
from collections.abc import Mapping
from typing import Any, Final

from celery import current_app
from django.db import IntegrityError, transaction

from hope_dedup_engine.apps.biographic.const import UPDATE_STATUS_TASK
from hope_dedup_engine.apps.biographic.exceptions import LifecycleConflictError
from hope_dedup_engine.apps.biographic.models import BiographicJob, BiographicRecord, BiographicSet

ANOTHER_SET_ACTIVE: Final[str] = "Another set in this program is being processed or awaiting approval."
LOCK_HELD: Final[str] = "Another task is already running for this program."
NO_RECORDS: Final[str] = "Cannot process a set without records."
QUEUE_FAILED: Final[str] = "Could not queue the processing task."

logger = logging.getLogger(__name__)

State = BiographicSet.State


def _queue(task_name: str, *args: Any, **kwargs: Any) -> None:
    current_app.send_task(task_name, args=list(args), kwargs=kwargs)


def _queue_status_update(dataset: BiographicSet) -> None:
    """Ask for the set's decision to be mirrored into Elasticsearch.

    The decision is already committed, so a broker failure must not turn it into
    an error the client would retry into a conflict. The next process run in the
    program reconciles statuses that never reached Elasticsearch.
    """
    try:
        _queue(UPDATE_STATUS_TASK, dataset.pk)
    except Exception:
        logger.exception("Could not queue the status update for biographic set %s", dataset.pk)


def add_records(dataset: BiographicSet, rows: list[dict[str, Any]]) -> int:
    """Add validated records to a pending set, replacing re-sent reference_pks.

    The set's row stays locked until commit, so `start_processing` cannot start the
    set mid-upload.
    """
    with transaction.atomic():
        locked = BiographicSet.objects.select_for_update().get(pk=dataset.pk)
        if locked.state != State.PENDING:
            raise LifecycleConflictError(f"Cannot add records to set in '{locked.get_state_display()}' state.")
        return BiographicRecord.objects.upsert_batch(dataset, rows)


def start_processing(dataset: BiographicSet, overrides: Mapping[str, Any]) -> BiographicJob:
    """Take the program's processing slot for `dataset` and queue its run.

    Refuses when the set is not pending or failed, has no records, another set in
    the program is active, or a task already holds the program's lock. The lock
    is the task's to release, in its `finally`, whatever the outcome.
    """
    if dataset.state not in BiographicSet.PROCESSABLE_STATES:
        raise LifecycleConflictError(f"Cannot process set in '{dataset.get_state_display()}' state.")
    if not dataset.records.exists():
        raise LifecycleConflictError(NO_RECORDS)
    group = dataset.group
    if group.sets.filter(state__in=BiographicSet.ACTIVE_STATES).exclude(pk=dataset.pk).exists():
        raise LifecycleConflictError(ANOTHER_SET_ACTIVE)
    if not group.acquire_processing_lock():
        raise LifecycleConflictError(LOCK_HELD)

    try:
        with transaction.atomic():
            dataset.transition(BiographicSet.PROCESSABLE_STATES, State.INDEXING, "process")
            job = BiographicJob.objects.create(dataset=dataset, config_overrides=dict(overrides))
    except IntegrityError:
        # Lost the race to another set: the one-active-set constraint fired.
        group.release_processing_lock()
        raise LifecycleConflictError(ANOTHER_SET_ACTIVE) from None
    except Exception:
        group.release_processing_lock()
        raise

    try:
        job.queue()
    except Exception:
        dataset.set_state(State.FAILED, error=QUEUE_FAILED)
        group.release_processing_lock()
        raise
    return job


def cancel(dataset: BiographicSet) -> None:
    """Abandon a pending or failed set."""
    was_failed = dataset.state == State.FAILED
    # A failed run may have indexed part of the set before it stopped, so the
    # documents have to be marked rejected like any other discarded set.
    dataset.transition(BiographicSet.CANCELABLE_STATES, State.CANCELED, "cancel", search_sync_pending=was_failed)
    if was_failed:
        _queue_status_update(dataset)


def decide(dataset: BiographicSet, target: BiographicSet.State) -> None:
    """Approve or reject a deduplicated set, freeing the program for the next one.

    The task released the program's lock when it finished; leaving the active
    states is what frees the slot.
    """
    verb = "approve" if target == State.APPROVED else "reject"
    dataset.transition((State.DEDUPLICATED,), target, verb, search_sync_pending=True)
    _queue_status_update(dataset)

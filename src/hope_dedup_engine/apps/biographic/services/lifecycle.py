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

from hope_dedup_engine.apps.biographic.const import REBUILD_INDEX_TASK, UPDATE_STATUS_TASK
from hope_dedup_engine.apps.biographic.exceptions import LifecycleConflictError
from hope_dedup_engine.apps.biographic.models import BiographicGroup, BiographicJob, BiographicRecord, BiographicSet
from hope_dedup_engine.apps.biographic.services.status import REBUILD_STATUS

ANOTHER_SET_ACTIVE: Final[str] = "Another set in this program is being processed or awaiting approval."
LOCK_HELD: Final[str] = "Another task is already running for this program."
NO_RECORDS: Final[str] = "Cannot process a set without records."
QUEUE_FAILED: Final[str] = "Could not queue the processing task."

logger = logging.getLogger(__name__)

State = BiographicSet.State

# Indexed, so there is something to search; a deduplicated set may be searched again.
SEARCHABLE_STATES = (State.INDEXED, State.DEDUPLICATED)

# Where each kind of run may start from, the state it takes the set to, and what the error calls it.
STARTS = {
    BiographicJob.Mode.FULL: (BiographicSet.PROCESSABLE_STATES, State.INDEXING, "process"),
    BiographicJob.Mode.INDEX: (BiographicSet.PROCESSABLE_STATES, State.INDEXING, "process"),
    BiographicJob.Mode.SEARCH: (SEARCHABLE_STATES, State.DEDUPLICATING, "search"),
}


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


def start_processing(
    dataset: BiographicSet, overrides: Mapping[str, Any], mode: BiographicJob.Mode = BiographicJob.Mode.FULL
) -> BiographicJob:
    """Take the program's processing slot for `dataset` and queue its run.

    Refuses when the set is not pending or failed, has no records, another set in
    the program is active, or a task already holds the program's lock. The lock
    is the task's to release, in its `finally`, whatever the outcome.

    `mode` is `FULL` for the API. An administrator may index only, which leaves
    the set `indexed` for a later `start_search`.
    """
    if dataset.state in BiographicSet.PROCESSABLE_STATES and not dataset.records.exists():
        raise LifecycleConflictError(NO_RECORDS)
    return _start(dataset, overrides, mode)


def start_search(dataset: BiographicSet, overrides: Mapping[str, Any]) -> BiographicJob:
    """Score an indexed set against the index as it is, without indexing it again.

    From `indexed` (indexed on its own, or by a run that stopped there) or from
    `deduplicated` (score it again before deciding). Findings are replaced.
    """
    return _start(dataset, overrides, BiographicJob.Mode.SEARCH)


def _start(dataset: BiographicSet, overrides: Mapping[str, Any], mode: BiographicJob.Mode) -> BiographicJob:
    allowed, target, verb = STARTS[mode]
    if dataset.state not in allowed:
        raise LifecycleConflictError(f"Cannot {verb} set in '{dataset.get_state_display()}' state.")
    group = dataset.group
    if group.sets.filter(state__in=BiographicSet.ACTIVE_STATES).exclude(pk=dataset.pk).exists():
        raise LifecycleConflictError(ANOTHER_SET_ACTIVE)
    if not group.acquire_processing_lock():
        raise LifecycleConflictError(LOCK_HELD)

    previous = dataset.state
    try:
        with transaction.atomic():
            dataset.transition(allowed, target, verb)
            job = BiographicJob.objects.create(dataset=dataset, config_overrides=dict(overrides), mode=mode)
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
        if mode == BiographicJob.Mode.SEARCH:
            # Nothing was touched yet, so the set goes back to where it was.
            dataset.set_state(State(previous), force=True)
        else:
            dataset.set_state(State.FAILED, error=QUEUE_FAILED)
        group.release_processing_lock()
        raise
    return job


def start_rebuild(group: BiographicGroup, dataset: BiographicSet | None = None) -> None:
    """Take the program's lock and queue a rebuild of its index from Postgres.

    Restores documents only; see `process.rebuild`. Refuses when a task already holds
    the lock, or when `dataset` has nothing to restore. The task releases the lock.
    """
    if dataset is not None and dataset.state not in REBUILD_STATUS:
        raise LifecycleConflictError(f"Cannot rebuild the index from set in '{dataset.get_state_display()}' state.")
    if not group.acquire_processing_lock():
        raise LifecycleConflictError(LOCK_HELD)
    try:
        _queue(REBUILD_INDEX_TASK, group.pk, dataset.pk if dataset else None)
    except Exception:
        group.release_processing_lock()
        raise


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

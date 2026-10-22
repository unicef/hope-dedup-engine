"""Celery tasks for biographic deduplication.

`process_biographic_dataset` is the biometric `find_duplicates` skeleton around
the biographic service: it owns the state changes, the notifications, the run log
and the program's lock, and leaves the work to `services.process`.
"""

import logging
import traceback
from dataclasses import dataclass, field
from typing import Any

import sentry_sdk
from celery import shared_task, states
from celery.exceptions import Ignore
from django.utils import timezone
from elasticsearch import ConnectionError as SearchConnectionError
from elasticsearch import ConnectionTimeout as SearchConnectionTimeout

from hope_dedup_engine.apps.api.models.jobs import GracefulJobCancellationError
from hope_dedup_engine.apps.api.utils.notification import (
    RESULT_SENT,
    ErrorMessage,
    WarningMessage,
    send_notification,
)
from hope_dedup_engine.apps.biographic.config import BiographicConfig, resolve_config
from hope_dedup_engine.apps.biographic.models import BiographicFinding, BiographicJob, BiographicSet
from hope_dedup_engine.apps.biographic.protocols import BiographicSearch
from hope_dedup_engine.apps.biographic.search.backend import ElasticsearchBiographicSearch
from hope_dedup_engine.apps.biographic.services import process, status

logger = logging.getLogger(__name__)

State = BiographicSet.State

# A task owns the set in these states, so it is the one to fail it.
RUNNING_STATES = (State.INDEXING, State.INDEXED, State.DEDUPLICATING)

STATUS_UPDATE_MAX_RETRIES = 5


def get_search() -> BiographicSearch:
    """Return the search backend. Patched by tests that drive the tasks with a fake."""
    return ElasticsearchBiographicSearch()


@dataclass
class RunLog:
    """What one run records about itself, filled in as it goes."""

    dataset: BiographicSet
    config: BiographicConfig | None = None
    records_indexed: int = 0
    records_truncated: int = 0
    notifications: list[dict[str, str]] = field(default_factory=list)

    def append(self, error: Exception | None = None) -> None:
        entry: dict[str, Any] = {
            "timestamp": timezone.now().isoformat(),
            "action": "deduplicate",
            "state": self.dataset.get_state_display(),
            "config": self.config.as_dict() if self.config else None,
            "records_indexed": self.records_indexed,
            # Counted, not accumulated: a run that stops mid-way has stored part
            # of its findings, and the log should say how many.
            "findings_created": BiographicFinding.objects.filter(dataset=self.dataset).count(),
            "records_truncated": self.records_truncated,
            "notifications": self.notifications,
        }
        if error:
            entry["error"] = "".join(traceback.format_exception(error))
        self.dataset.append_log(entry)


def _notify(run: RunLog) -> None:
    """Notify the client about the current state and record whether it went through."""
    dataset = run.dataset
    result = send_notification(dataset)
    if isinstance(result, ErrorMessage):
        logger.error("Notification failed for biographic set %s: %s", dataset.pk, result)
    elif isinstance(result, WarningMessage):
        logger.warning("Notification skipped for biographic set %s: %s", dataset.pk, result)
    run.notifications.append(
        {
            "state": dataset.get_state_display(),
            "result": result if isinstance(result, str) else RESULT_SENT,
        }
    )


def _fail(dataset: BiographicSet, error: Exception) -> None:
    """Fail the set unless something else already moved it, like an admin's "Mark as failed"."""
    dataset.refresh_from_db(fields=["state", "error"])
    if dataset.state in RUNNING_STATES:
        dataset.set_state(State.FAILED, error=str(error) or type(error).__name__)


def _revoke_cancelled_task(task: Any, job: BiographicJob, error: GracefulJobCancellationError) -> None:
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
def process_biographic_dataset(self: Any, job_id: int, version: int) -> dict[str, Any]:
    """Index a set, score it against itself and the approved population, store the findings.

    State transitions:
        INDEXING -> INDEXED -> DEDUPLICATING -> DEDUPLICATED
    On failure or graceful cancellation, from any of the first three:
        -> FAILED

    The program's lock is taken by the caller before queueing and released here,
    in `finally`, whatever happens.
    """
    job = BiographicJob.objects.select_related("dataset__group").get(pk=job_id, version=version)
    dataset = job.dataset
    group = dataset.group
    search = get_search()
    run = RunLog(dataset)

    try:
        job.ensure_not_cancelled()
        _notify(run)
        run.config = resolve_config(dataset, job.config_overrides)

        process.prepare(dataset, search)
        run.records_indexed = process.index(dataset, search, job)
        dataset.set_state(State.INDEXED)
        _notify(run)

        dataset.set_state(State.DEDUPLICATING)
        _notify(run)
        stats = process.deduplicate(dataset, run.config, search, job)
        run.records_truncated = stats.records_truncated

        dataset.set_state(State.DEDUPLICATED)
        _notify(run)
        run.append()
        return {
            "dataset": dataset.pk,
            "records_indexed": run.records_indexed,
            "findings_created": stats.findings_created,
            "records_truncated": stats.records_truncated,
        }
    except GracefulJobCancellationError as e:
        logger.info("Task cancelled gracefully for BiographicJob #%s", job.pk)
        _fail(dataset, e)
        _notify(run)
        run.append(error=e)
        _revoke_cancelled_task(self, job, e)
        raise Ignore from e
    except Exception as e:
        _fail(dataset, e)
        _notify(run)
        run.append(error=e)
        sentry_sdk.capture_exception(e)
        raise
    finally:
        group.release_processing_lock()


@shared_task(
    autoretry_for=(SearchConnectionError, SearchConnectionTimeout),
    retry_backoff=True,
    retry_kwargs={"max_retries": STATUS_UPDATE_MAX_RETRIES},
)
def update_biographic_status(dataset_id: int) -> int:
    """Mirror a set's decision into Elasticsearch. Returns the documents updated.

    Retried on a connection failure. If it still fails, `search_sync_pending`
    stays set and the next run in the program reconciles it.
    """
    dataset = BiographicSet.objects.select_related("group").get(pk=dataset_id)
    return status.sync(dataset, get_search())


@shared_task
def cleanup_biographic_rejected() -> dict[str, int]:
    """Delete rejected documents from every biographic index. Runs daily from beat."""
    deleted = get_search().delete_by_status(status.STATUS_REJECTED)
    for name, count in deleted.items():
        if count:
            logger.info("Deleted %s rejected biographic documents from %s", count, name)
    return deleted

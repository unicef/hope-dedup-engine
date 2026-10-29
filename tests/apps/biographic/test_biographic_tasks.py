"""The Celery tasks, run in-process against the in-memory search."""

import pytest
from celery.exceptions import Ignore
from django_celery_beat.models import PeriodicTask
from testutils.biographic import make_payload
from testutils.factories.biographic import BiographicJobFactory, BiographicRecordFactory, BiographicSetFactory

from hope_dedup_engine.apps.api.models.jobs import GracefulJobCancellationError
from hope_dedup_engine.apps.api.utils.notification import (
    FAILED_TO_NOTIFY,
    NOTIFICATION_DISABLED,
    ErrorMessage,
    WarningMessage,
)
from hope_dedup_engine.apps.biographic import celery_tasks
from hope_dedup_engine.apps.biographic.const import (
    CLEANUP_REJECTED_PERIODIC_TASK_NAME,
    CLEANUP_REJECTED_TASK,
    PROCESS_DATASET_TASK,
    REBUILD_INDEX_TASK,
    UPDATE_STATUS_TASK,
)
from hope_dedup_engine.apps.biographic.exceptions import IndexMissingError
from hope_dedup_engine.apps.biographic.models import BiographicFinding, BiographicJob, BiographicSet
from hope_dedup_engine.apps.biographic.services import process

pytestmark = pytest.mark.django_db

State = BiographicSet.State


@pytest.fixture
def job(no_tracking, fake_search, sent_notifications) -> BiographicJob:
    job = BiographicJobFactory(
        dataset__group__processing_locked=True,
        dataset__notification_url="https://hope.example.org/callback/",
    )
    BiographicRecordFactory(dataset=job.dataset, reference_pk="a", payload={"full_name": "Ana Silva"})
    BiographicRecordFactory(dataset=job.dataset, reference_pk="b", payload={"full_name": "Ana Silva"})
    return job


def run(job: BiographicJob):
    return celery_tasks.process_biographic_dataset(job.pk, job.version)


def locked(dataset: BiographicSet) -> bool:
    dataset.group.refresh_from_db()
    return dataset.group.processing_locked


def test_task_names_match_the_constants():
    assert celery_tasks.process_biographic_dataset.name == PROCESS_DATASET_TASK
    assert celery_tasks.update_biographic_status.name == UPDATE_STATUS_TASK
    assert celery_tasks.cleanup_biographic_rejected.name == CLEANUP_REJECTED_TASK
    assert celery_tasks.rebuild_biographic_index.name == REBUILD_INDEX_TASK
    assert BiographicJob.celery_task_name == PROCESS_DATASET_TASK


# --- process_biographic_dataset -----------------------------------------------


def test_a_full_run(job, sent_notifications):
    dataset = job.dataset

    result = run(job)

    dataset.refresh_from_db()
    assert dataset.state == State.DEDUPLICATED
    assert dataset.error is None
    assert result == {"dataset": dataset.pk, "records_indexed": 2, "findings_created": 2, "records_truncated": 0}
    assert BiographicFinding.objects.filter(dataset=dataset).count() == 2
    assert not locked(dataset)

    assert [c.args[0] for c in sent_notifications.call_args_list] == [dataset] * 4
    (entry,) = dataset.log
    assert entry["action"] == "deduplicate"
    assert entry["state"] == "Deduplicated"
    assert entry["config"]["duplicate_score"] == 6.0
    assert (entry["records_indexed"], entry["findings_created"], entry["records_truncated"]) == (2, 2, 0)
    assert "error" not in entry
    assert entry["notifications"] == [
        {"state": "Indexing", "result": "sent"},
        {"state": "Indexed", "result": "sent"},
        {"state": "Deduplicating", "result": "sent"},
        {"state": "Deduplicated", "result": "sent"},
    ]


def test_a_run_uses_the_jobs_overrides(job, fake_search):
    job.config_overrides = {"duplicate_score": 12.0}
    job.save()

    result = run(job)

    assert result["findings_created"] == 0
    job.dataset.refresh_from_db()
    assert job.dataset.log[0]["config"]["duplicate_score"] == 12.0


def test_undelivered_notifications_are_in_the_log(job, sent_notifications):
    sent_notifications.side_effect = [
        WarningMessage(NOTIFICATION_DISABLED),
        ErrorMessage(FAILED_TO_NOTIFY.format(error="timeout")),
        None,
        None,
    ]

    run(job)

    job.dataset.refresh_from_db()
    assert [n["result"] for n in job.dataset.log[0]["notifications"]] == [
        NOTIFICATION_DISABLED,
        FAILED_TO_NOTIFY.format(error="timeout"),
        "sent",
        "sent",
    ]


@pytest.mark.parametrize("case", [("index_records", "Indexing"), ("search_many", "Deduplicating")])
def test_a_failure_fails_the_set_logs_the_traceback_and_releases_the_lock(job, fake_search, mocker, case):
    failing_step, state_when_failed = case
    fake_search.fail_on = failing_step
    capture = mocker.patch.object(celery_tasks.sentry_sdk, "capture_exception")
    dataset = job.dataset

    with pytest.raises(RuntimeError, match=f"{failing_step} failed"):
        run(job)

    dataset.refresh_from_db()
    assert dataset.state == State.FAILED
    assert dataset.error == f"{failing_step} failed"
    assert not locked(dataset)
    (entry,) = dataset.log
    assert entry["state"] == "Failed"
    assert f"RuntimeError: {failing_step} failed" in entry["error"]
    assert [n["state"] for n in entry["notifications"]][-2:] == [state_when_failed, "Failed"]
    capture.assert_called_once()


def test_a_failed_run_can_be_retried_cleanly(job, fake_search):
    fake_search.fail_on = "search_many"
    with pytest.raises(RuntimeError):
        run(job)
    fake_search.fail_on = None
    dataset = BiographicSet.objects.get(pk=job.dataset_id)
    dataset.set_state(State.INDEXING)
    retry = BiographicJobFactory(dataset=dataset)

    run(retry)

    dataset.refresh_from_db()
    assert dataset.state == State.DEDUPLICATED
    assert BiographicFinding.objects.filter(dataset=dataset).count() == 2
    assert len(dataset.log) == 2


def test_a_graceful_cancellation_fails_the_set_and_revokes_the_task(job, mocker):
    mocker.patch.object(BiographicJob, "is_termination_requested", new_callable=mocker.PropertyMock, return_value=True)
    cancel = mocker.patch.object(BiographicJob, "cancel")
    update_state = mocker.patch.object(celery_tasks.process_biographic_dataset, "update_state")
    dataset = job.dataset

    with pytest.raises(Ignore):
        run(job)

    dataset.refresh_from_db()
    assert dataset.state == State.FAILED
    assert "Cancellation requested" in dataset.error
    assert not locked(dataset)
    assert "GracefulJobCancellationError" in dataset.log[0]["error"]
    cancel.assert_called_once()
    assert update_state.call_args.kwargs["state"] == "REVOKED"


def test_a_cancellation_mid_search_keeps_the_partial_findings_count(job, mocker):
    mocker.patch.object(process, "SEARCH_CHUNK_SIZE", 1)
    mocker.patch.object(BiographicJob, "cancel")
    mocker.patch.object(celery_tasks.process_biographic_dataset, "update_state")
    original = BiographicJob.ensure_not_cancelled
    calls = {"n": 0}

    def ensure(self):
        calls["n"] += 1
        # First call: task start. Second: first index chunk. Third: first search chunk.
        if calls["n"] == 4:
            raise GracefulJobCancellationError("stop")
        original(self)

    mocker.patch.object(BiographicJob, "ensure_not_cancelled", ensure)

    with pytest.raises(Ignore):
        run(job)

    job.dataset.refresh_from_db()
    entry = job.dataset.log[0]
    assert (entry["records_indexed"], entry["findings_created"]) == (2, 1)


def test_a_set_already_failed_by_an_admin_is_left_alone(job, fake_search, mocker):
    """`Mark as failed` ran while the worker was still going: do not fight it."""
    fake_search.fail_on = "search_many"
    original = fake_search.search_many

    def mark_failed_then_fail(*args, **kwargs):
        BiographicSet.objects.filter(pk=job.dataset.pk).update(state=State.FAILED, error="Marked by admin")
        return original(*args, **kwargs)

    mocker.patch.object(fake_search, "search_many", mark_failed_then_fail)

    with pytest.raises(RuntimeError):
        run(job)

    job.dataset.refresh_from_db()
    assert job.dataset.error == "Marked by admin"


def test_a_stale_job_version_is_refused(job):
    with pytest.raises(BiographicJob.DoesNotExist):
        celery_tasks.process_biographic_dataset(job.pk, job.version + 1)


# --- partial runs ---------------------------------------------------------------


def test_an_index_run_stops_at_indexed(job, fake_search, sent_notifications):
    job.mode = BiographicJob.Mode.INDEX
    job.save()
    dataset = job.dataset

    result = run(job)

    dataset.refresh_from_db()
    assert dataset.state == State.INDEXED
    assert result == {"dataset": dataset.pk, "records_indexed": 2}
    assert not BiographicFinding.objects.filter(dataset=dataset).exists()
    assert not locked(dataset)
    assert not any(call[0] == "search_many" for call in fake_search.calls)
    (entry,) = dataset.log
    assert (entry["action"], entry["state"], entry["records_indexed"]) == ("index", "Indexed", 2)
    assert [c.args[0] for c in sent_notifications.call_args_list] == [dataset] * 2


def test_a_search_run_scores_what_an_index_run_left_behind(job, fake_search, sent_notifications):
    job.mode = BiographicJob.Mode.INDEX
    job.save()
    run(job)
    dataset = job.dataset
    dataset.refresh_from_db()
    dataset.set_state(State.DEDUPLICATING)
    dataset.group.acquire_processing_lock()
    search_job = BiographicJob.objects.create(dataset=dataset, mode=BiographicJob.Mode.SEARCH)
    fake_search.calls.clear()

    result = run(search_job)

    dataset.refresh_from_db()
    assert dataset.state == State.DEDUPLICATED
    assert result == {"dataset": dataset.pk, "records_indexed": 0, "findings_created": 2, "records_truncated": 0}
    assert BiographicFinding.objects.filter(dataset=dataset).count() == 2
    assert not locked(dataset)
    assert not any(call[0] == "index_records" for call in fake_search.calls)
    assert dataset.log[-1]["action"] == "search"
    assert [n["state"] for n in dataset.log[-1]["notifications"]] == ["Deduplicating", "Deduplicated"]


def test_a_search_run_fails_the_set_when_its_index_is_gone(job, fake_search):
    job.mode = BiographicJob.Mode.SEARCH
    job.save()
    dataset = job.dataset
    dataset.set_state(State.DEDUPLICATING, force=True)

    with pytest.raises(IndexMissingError):
        run(job)

    dataset.refresh_from_db()
    assert dataset.state == State.FAILED
    assert "Rebuild the index" in dataset.error
    assert not locked(dataset)


# --- rebuild_biographic_index ---------------------------------------------------


def test_rebuild_restores_the_sets_logs_it_and_releases_the_lock(fake_search):
    approved = BiographicSetFactory(state=State.APPROVED, group__processing_locked=True)
    BiographicRecordFactory(dataset=approved, reference_pk="a", payload={"full_name": "Ana Silva"})
    group = approved.group

    written = celery_tasks.rebuild_biographic_index(group.pk)

    assert written == {approved.pk: 1}
    assert fake_search.documents(group.business_area, group.program_code)[f"{approved.pk}:a"].status == "approved"
    approved.refresh_from_db()
    assert (approved.log[0]["action"], approved.log[0]["records_indexed"]) == ("rebuild_index", 1)
    assert not locked(approved)


def test_rebuild_of_one_set_only_restores_that_set(fake_search):
    group = BiographicSetFactory(group__processing_locked=True).group
    first = BiographicSetFactory(group=group, state=State.APPROVED)
    second = BiographicSetFactory(group=group, state=State.APPROVED)
    BiographicRecordFactory(dataset=first, reference_pk="a")
    BiographicRecordFactory(dataset=second, reference_pk="b")

    assert celery_tasks.rebuild_biographic_index(group.pk, second.pk) == {second.pk: 1}


def test_a_failed_rebuild_still_releases_the_lock(fake_search):
    group = BiographicSetFactory(group__processing_locked=True).group
    fake_search.fail_on = "ensure_index"

    with pytest.raises(RuntimeError, match="ensure_index failed"):
        celery_tasks.rebuild_biographic_index(group.pk)

    group.refresh_from_db()
    assert not group.processing_locked


# --- update_biographic_status -------------------------------------------------


def test_update_status_syncs_the_decision(fake_search):
    dataset = BiographicSetFactory(state=State.APPROVED, search_sync_pending=True)
    group = dataset.group
    fake_search.ensure_index(group.business_area, group.program_code)
    fake_search.index_records(group.business_area, group.program_code, dataset.pk, [make_payload("a")])

    assert celery_tasks.update_biographic_status(dataset.pk) == 1

    assert fake_search.documents(group.business_area, group.program_code)[f"{dataset.pk}:a"].status == "approved"
    dataset.refresh_from_db()
    assert not dataset.search_sync_pending


def test_update_status_retries_on_connection_errors():
    assert celery_tasks.update_biographic_status.autoretry_for == (
        celery_tasks.SearchConnectionError,
        celery_tasks.SearchConnectionTimeout,
    )
    assert celery_tasks.update_biographic_status.retry_kwargs == {"max_retries": celery_tasks.STATUS_UPDATE_MAX_RETRIES}


# --- cleanup_biographic_rejected ----------------------------------------------


def test_cleanup_deletes_rejected_documents_everywhere_and_logs_counts(fake_search, mocker):
    rejected = BiographicSetFactory(state=State.REJECTED)
    approved = BiographicSetFactory(state=State.APPROVED)
    for dataset, status in ((rejected, "rejected"), (approved, "approved")):
        group = dataset.group
        fake_search.ensure_index(group.business_area, group.program_code)
        fake_search.index_records(group.business_area, group.program_code, dataset.pk, [make_payload("a")])
        fake_search.set_status(group.business_area, group.program_code, dataset.pk, status)
    logger = mocker.patch.object(celery_tasks, "logger")

    deleted = celery_tasks.cleanup_biographic_rejected()

    assert deleted == {
        fake_search.index_name(rejected.group.business_area, rejected.group.program_code): 1,
        fake_search.index_name(approved.group.business_area, approved.group.program_code): 0,
    }
    assert not fake_search.documents(rejected.group.business_area, rejected.group.program_code)
    assert len(fake_search.documents(approved.group.business_area, approved.group.program_code)) == 1
    logger.info.assert_called_once()


def test_cleanup_is_scheduled_daily_by_the_migration():
    task = PeriodicTask.objects.get(name=CLEANUP_REJECTED_PERIODIC_TASK_NAME)
    assert task.task == CLEANUP_REJECTED_TASK
    assert task.enabled
    assert task.queue == "queue_hde"
    assert (task.crontab.minute, task.crontab.hour, task.crontab.day_of_week) == ("0", "2", "*")

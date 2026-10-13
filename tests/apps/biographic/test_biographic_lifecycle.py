"""The lifecycle rules, exercised directly. The API tests cover the same rules over HTTP."""

import pytest
from django.db import IntegrityError
from testutils.factories.biographic import BiographicRecordFactory, BiographicSetFactory

from hope_dedup_engine.apps.biographic.const import PROCESS_DATASET_TASK, UPDATE_STATUS_TASK
from hope_dedup_engine.apps.biographic.exceptions import InvalidTransitionError, LifecycleConflictError
from hope_dedup_engine.apps.biographic.models import BiographicGroup, BiographicSet
from hope_dedup_engine.apps.biographic.services import lifecycle
from hope_dedup_engine.apps.biographic.services.lifecycle import ANOTHER_SET_ACTIVE, LOCK_HELD, NO_RECORDS, QUEUE_FAILED

pytestmark = pytest.mark.django_db

State = BiographicSet.State


def locked(group: BiographicGroup) -> bool:
    group.refresh_from_db()
    return group.processing_locked


@pytest.fixture
def pending() -> BiographicSet:
    dataset = BiographicSetFactory()
    BiographicRecordFactory(dataset=dataset)
    return dataset


# --- add_records --------------------------------------------------------------


def test_add_records_writes_into_a_pending_set():
    dataset = BiographicSetFactory()
    received = lifecycle.add_records(dataset, [{"reference_pk": "cw-1", "payload": {}}])
    assert received == 1
    assert dataset.records.count() == 1


@pytest.mark.parametrize("state", [s for s in State if s != State.PENDING])
def test_add_records_refuses_a_set_that_is_not_pending(state):
    dataset = BiographicSetFactory(state=state)
    with pytest.raises(LifecycleConflictError, match="Cannot add records"):
        lifecycle.add_records(dataset, [{"reference_pk": "cw-1", "payload": {}}])
    assert not dataset.records.exists()


# --- start_processing ---------------------------------------------------------


def test_start_processing_takes_the_slot_and_queues_the_run(pending, queued_tasks):
    lifecycle.start_processing(pending, {"max_hits": 5})

    assert pending.state == State.INDEXING
    assert locked(pending.group)
    queued_tasks.assert_called_once_with(
        PROCESS_DATASET_TASK, args=[pending.pk], kwargs={"config_overrides": {"max_hits": 5}}
    )


@pytest.mark.parametrize("state", [s for s in State if s not in BiographicSet.PROCESSABLE_STATES])
def test_start_processing_needs_a_pending_or_failed_set(state, queued_tasks):
    dataset = BiographicSetFactory(state=state)
    BiographicRecordFactory(dataset=dataset)
    with pytest.raises(LifecycleConflictError, match="Cannot process"):
        lifecycle.start_processing(dataset, {})
    assert not locked(dataset.group)
    queued_tasks.assert_not_called()


def test_start_processing_needs_records(queued_tasks):
    dataset = BiographicSetFactory()
    with pytest.raises(LifecycleConflictError, match=NO_RECORDS):
        lifecycle.start_processing(dataset, {})
    assert not locked(dataset.group)


@pytest.mark.parametrize("active", BiographicSet.ACTIVE_STATES)
def test_start_processing_refuses_while_another_set_is_active(pending, active, queued_tasks):
    BiographicSetFactory(group=pending.group, state=active)
    with pytest.raises(LifecycleConflictError, match=ANOTHER_SET_ACTIVE):
        lifecycle.start_processing(pending, {})
    pending.refresh_from_db()
    assert pending.state == State.PENDING


def test_start_processing_refuses_when_a_task_holds_the_lock(pending, queued_tasks):
    BiographicGroup.objects.filter(pk=pending.group_id).update(processing_locked=True)
    with pytest.raises(LifecycleConflictError, match=LOCK_HELD):
        lifecycle.start_processing(pending, {})
    queued_tasks.assert_not_called()


def test_start_processing_losing_the_slot_race_releases_the_lock(pending, queued_tasks, mocker):
    mocker.patch.object(BiographicSet, "set_state", side_effect=IntegrityError)
    with pytest.raises(LifecycleConflictError, match=ANOTHER_SET_ACTIVE):
        lifecycle.start_processing(pending, {})
    assert not locked(pending.group)
    queued_tasks.assert_not_called()


def test_start_processing_unexpected_error_releases_the_lock(pending, queued_tasks, mocker):
    mocker.patch.object(BiographicSet, "set_state", side_effect=RuntimeError("db gone"))
    with pytest.raises(RuntimeError):
        lifecycle.start_processing(pending, {})
    assert not locked(pending.group)


def test_start_processing_queue_failure_fails_the_set_and_releases_the_lock(pending, queued_tasks):
    queued_tasks.side_effect = ConnectionError("broker down")
    with pytest.raises(ConnectionError):
        lifecycle.start_processing(pending, {})
    pending.refresh_from_db()
    assert (pending.state, pending.error) == (State.FAILED, QUEUE_FAILED)
    assert not locked(pending.group)


# --- cancel -------------------------------------------------------------------


def test_cancel_a_pending_set_queues_nothing(pending, queued_tasks):
    lifecycle.cancel(pending)
    assert pending.state == State.CANCELED
    queued_tasks.assert_not_called()


def test_cancel_a_failed_set_asks_for_cleanup(queued_tasks):
    dataset = BiographicSetFactory(state=State.FAILED)
    lifecycle.cancel(dataset)
    assert dataset.state == State.CANCELED
    queued_tasks.assert_called_once_with(UPDATE_STATUS_TASK, args=[dataset.pk], kwargs={})


@pytest.mark.parametrize("state", [s for s in State if s not in BiographicSet.CANCELABLE_STATES])
def test_cancel_refuses_other_states(state, queued_tasks):
    dataset = BiographicSetFactory(state=state)
    with pytest.raises(InvalidTransitionError, match="Cannot cancel"):
        lifecycle.cancel(dataset)
    queued_tasks.assert_not_called()


# --- decide -------------------------------------------------------------------


@pytest.mark.parametrize("target", [State.APPROVED, State.REJECTED])
def test_decide_releases_the_lock_and_queues_the_status_update(target, queued_tasks):
    dataset = BiographicSetFactory(state=State.DEDUPLICATED, group__processing_locked=True)
    lifecycle.decide(dataset, target)
    assert dataset.state == target
    assert not locked(dataset.group)
    queued_tasks.assert_called_once_with(UPDATE_STATUS_TASK, args=[dataset.pk], kwargs={})


@pytest.mark.parametrize("target", [State.APPROVED, State.REJECTED])
@pytest.mark.parametrize("state", [s for s in State if s != State.DEDUPLICATED])
def test_decide_needs_a_deduplicated_set(state, target, queued_tasks):
    dataset = BiographicSetFactory(state=state, group__processing_locked=True)
    with pytest.raises(InvalidTransitionError):
        lifecycle.decide(dataset, target)
    assert locked(dataset.group)
    queued_tasks.assert_not_called()


def test_decide_stands_when_the_status_update_cannot_be_queued(queued_tasks, mocker):
    dataset = BiographicSetFactory(state=State.DEDUPLICATED)
    queued_tasks.side_effect = ConnectionError("broker down")
    logger = mocker.patch.object(lifecycle, "logger")

    lifecycle.decide(dataset, State.APPROVED)

    assert dataset.state == State.APPROVED
    logger.exception.assert_called_once()

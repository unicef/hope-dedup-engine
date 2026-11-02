from itertools import product

import pytest
from django.db import IntegrityError, transaction
from testutils.factories.biographic import (
    BiographicFindingFactory,
    BiographicGroupFactory,
    BiographicJobFactory,
    BiographicRecordFactory,
    BiographicSetFactory,
)

from hope_dedup_engine.apps.api.models.deduplication import MAX_ERROR_LENGTH
from hope_dedup_engine.apps.api.models.jobs import GracefulJobCancellationError
from hope_dedup_engine.apps.biographic.const import PROCESS_DATASET_TASK
from hope_dedup_engine.apps.biographic.exceptions import InvalidTransitionError
from hope_dedup_engine.apps.biographic.models import (
    FULL_NAME_LENGTH,
    BiographicFinding,
    BiographicGroup,
    BiographicJob,
    BiographicRecord,
    BiographicSet,
)
from hope_dedup_engine.apps.biographic.schemas import PAYLOAD_VERSION

pytestmark = pytest.mark.django_db

State = BiographicSet.State

VALID = [(source, target) for source, targets in BiographicSet.VALID_TRANSITIONS.items() for target in targets]
INVALID = [(source, target) for source, target in product(State, State) if (source, target) not in VALID]


def test_every_state_has_a_transition_entry():
    assert set(BiographicSet.VALID_TRANSITIONS) == set(State)


def test_terminal_states_have_no_way_out():
    for state in (State.APPROVED, State.REJECTED, State.CANCELED):
        assert BiographicSet.VALID_TRANSITIONS[state] == ()


def test_group_is_unique_per_business_area_and_program():
    BiographicGroupFactory(business_area="afg", program_code="ab12")
    with pytest.raises(IntegrityError):
        BiographicGroupFactory(business_area="afg", program_code="ab12")


def test_one_business_area_can_hold_many_programs():
    BiographicGroupFactory(business_area="afg", program_code="ab12")
    BiographicGroupFactory(business_area="afg", program_code="cd34")
    assert BiographicGroup.objects.filter(business_area="afg").count() == 2


def test_lock_is_exclusive_and_released():
    group = BiographicGroupFactory()
    assert group.acquire_processing_lock() is True
    assert group.acquire_processing_lock() is False
    group.release_processing_lock()
    group.refresh_from_db()
    assert group.processing_locked is False
    assert group.acquire_processing_lock() is True


def test_two_programs_in_one_business_area_lock_independently():
    first = BiographicGroupFactory(business_area="afg", program_code="ab12")
    second = BiographicGroupFactory(business_area="afg", program_code="cd34")
    assert first.acquire_processing_lock() is True
    assert second.acquire_processing_lock() is True


def test_lock_reads_the_database_not_the_instance():
    group = BiographicGroupFactory()
    stale = BiographicGroup.objects.get(pk=group.pk)
    assert group.acquire_processing_lock() is True
    assert stale.acquire_processing_lock() is False


@pytest.mark.parametrize(("source", "target"), VALID, ids=[f"{s}->{t}" for s, t in VALID])
def test_valid_transition(source, target):
    dataset = BiographicSetFactory(state=source)
    dataset.set_state(target)
    dataset.refresh_from_db()
    assert dataset.state == target


@pytest.mark.parametrize(("source", "target"), INVALID, ids=[f"{s}->{t}" for s, t in INVALID])
def test_invalid_transition(source, target):
    dataset = BiographicSetFactory(state=source)
    with pytest.raises(ValueError, match="Invalid state transition"):
        dataset.set_state(target)
    dataset.refresh_from_db()
    assert dataset.state == source


def test_reject_after_approve_is_refused():
    dataset = BiographicSetFactory(state=State.DEDUPLICATED)
    dataset.set_state(State.APPROVED)
    with pytest.raises(ValueError, match="Approved -> Rejected"):
        dataset.set_state(State.REJECTED)


def test_force_bypasses_the_transition_table():
    dataset = BiographicSetFactory(state=State.DEDUPLICATING)
    dataset.set_state(State.PENDING, force=True)
    dataset.refresh_from_db()
    assert dataset.state == State.PENDING


def test_failure_records_a_truncated_error_and_the_next_run_clears_it():
    dataset = BiographicSetFactory(state=State.INDEXING)
    dataset.set_state(State.FAILED, error="x" * (MAX_ERROR_LENGTH + 50))
    dataset.refresh_from_db()
    assert dataset.error == "x" * MAX_ERROR_LENGTH

    dataset.set_state(State.INDEXING)
    dataset.refresh_from_db()
    assert dataset.error is None


@pytest.mark.parametrize("first", BiographicSet.ACTIVE_STATES)
@pytest.mark.parametrize("second", BiographicSet.ACTIVE_STATES)
def test_one_active_set_per_group(first, second):
    group = BiographicGroupFactory()
    BiographicSetFactory(group=group, state=first)
    with pytest.raises(IntegrityError), transaction.atomic():
        BiographicSetFactory(group=group, state=second)


@pytest.mark.parametrize("state", [State.PENDING, State.FAILED, State.APPROVED, State.REJECTED, State.CANCELED])
def test_inactive_sets_do_not_take_the_slot(state):
    group = BiographicGroupFactory()
    BiographicSetFactory(group=group, state=state)
    BiographicSetFactory(group=group, state=state)
    BiographicSetFactory(group=group, state=State.DEDUPLICATING)
    assert group.sets.count() == 3


def test_active_sets_in_different_groups_coexist():
    BiographicSetFactory(state=State.DEDUPLICATING)
    BiographicSetFactory(state=State.DEDUPLICATING)
    assert BiographicSet.objects.filter(state=State.DEDUPLICATING).count() == 2


def test_transition_moves_a_set_that_is_in_an_allowed_state():
    dataset = BiographicSetFactory(state=State.PENDING, error="old")

    dataset.transition(BiographicSet.PROCESSABLE_STATES, State.INDEXING, "process")

    dataset.refresh_from_db()
    assert dataset.state == State.INDEXING
    assert dataset.error is None


def test_transition_refuses_a_set_outside_the_allowed_states():
    dataset = BiographicSetFactory(state=State.DEDUPLICATED)

    with pytest.raises(InvalidTransitionError, match="Cannot process set in 'Deduplicated' state."):
        dataset.transition(BiographicSet.PROCESSABLE_STATES, State.INDEXING, "process")

    dataset.refresh_from_db()
    assert dataset.state == State.DEDUPLICATED


def test_transition_checks_the_database_not_the_instance():
    dataset = BiographicSetFactory(state=State.PENDING)
    BiographicSet.objects.filter(pk=dataset.pk).update(state=State.CANCELED)

    with pytest.raises(InvalidTransitionError):
        dataset.transition(BiographicSet.PROCESSABLE_STATES, State.INDEXING, "process")


def test_transition_can_flag_the_search_sync_with_the_state():
    dataset = BiographicSetFactory(state=State.DEDUPLICATED)

    dataset.transition((State.DEDUPLICATED,), State.APPROVED, "approve", search_sync_pending=True)

    assert dataset.search_sync_pending
    assert BiographicSet.objects.get(pk=dataset.pk).search_sync_pending


def test_transition_does_not_flag_the_sync_when_refused():
    dataset = BiographicSetFactory(state=State.PENDING)
    with pytest.raises(InvalidTransitionError):
        dataset.transition((State.DEDUPLICATED,), State.APPROVED, "approve", search_sync_pending=True)
    assert not BiographicSet.objects.get(pk=dataset.pk).search_sync_pending


def test_append_log_keeps_earlier_entries():
    dataset = BiographicSetFactory(log=[{"action": "first"}])
    dataset.append_log({"action": "second"})
    assert [e["action"] for e in BiographicSet.objects.get(pk=dataset.pk).log] == ["first", "second"]


def test_a_job_belongs_to_its_set_and_knows_its_task():
    job = BiographicJobFactory(config_overrides={"max_hits": 3})
    assert list(job.dataset.jobs.all()) == [job]
    assert job.celery_task_name == PROCESS_DATASET_TASK
    assert str(job) == f"Job {job.pk} for set {job.dataset_id}"


def test_a_job_raises_when_termination_was_requested(mocker):
    job = BiographicJobFactory()
    mocker.patch.object(BiographicJob, "is_termination_requested", new_callable=mocker.PropertyMock, return_value=True)
    with pytest.raises(GracefulJobCancellationError):
        job.ensure_not_cancelled()


def test_reference_pk_is_unique_within_a_set_only():
    record = BiographicRecordFactory(reference_pk="cw-1")
    BiographicRecordFactory(reference_pk="cw-1")
    with pytest.raises(IntegrityError):
        BiographicRecordFactory(dataset=record.dataset, reference_pk="cw-1")


def test_upsert_batch_inserts_and_copies_the_full_name():
    dataset = BiographicSetFactory()
    rows = [
        {"reference_pk": "cw-1", "payload": {"full_name": "Maria Gonzalez", "sex": "F"}},
        {"reference_pk": "cw-2", "payload": {"given_name": "Ali"}},
    ]

    assert BiographicRecord.objects.upsert_batch(dataset, rows) == 2

    by_pk = {r.reference_pk: r for r in dataset.records.all()}
    assert by_pk["cw-1"].full_name == "Maria Gonzalez"
    assert by_pk["cw-1"].payload == rows[0]["payload"]
    assert by_pk["cw-1"].payload_version == PAYLOAD_VERSION
    assert by_pk["cw-2"].full_name == ""


def test_upsert_batch_replaces_a_resent_reference_pk_in_place():
    dataset = BiographicSetFactory()
    BiographicRecord.objects.upsert_batch(dataset, [{"reference_pk": "cw-1", "payload": {"full_name": "Old"}}])
    original_pk = dataset.records.get().pk

    received = BiographicRecord.objects.upsert_batch(
        dataset, [{"reference_pk": "cw-1", "payload": {"full_name": "New"}}]
    )

    assert received == 1
    record = dataset.records.get()
    assert record.pk == original_pk
    assert record.full_name == "New"
    assert record.payload == {"full_name": "New"}


def test_upsert_batch_truncates_an_overlong_full_name():
    dataset = BiographicSetFactory()
    BiographicRecord.objects.upsert_batch(dataset, [{"reference_pk": "cw-1", "payload": {"full_name": "x" * 300}}])
    assert len(dataset.records.get().full_name) == FULL_NAME_LENGTH


def test_a_pair_is_stored_once_per_scope():
    finding = BiographicFindingFactory(scope=BiographicFinding.Scope.BATCH)
    BiographicFindingFactory(
        record=finding.record,
        matched_reference_pk=finding.matched_reference_pk,
        scope=BiographicFinding.Scope.POPULATION,
    )
    with pytest.raises(IntegrityError):
        BiographicFindingFactory(
            record=finding.record,
            matched_reference_pk=finding.matched_reference_pk,
            scope=BiographicFinding.Scope.BATCH,
        )


def test_string_representations():
    finding = BiographicFindingFactory(
        record__reference_pk="cw-1",
        record__dataset__group__business_area="afg",
        record__dataset__group__program_code="ab12",
        matched_reference_pk="cw-2",
    )
    assert str(finding.dataset.group) == "afg:ab12"
    assert str(finding.dataset) == f"ID: {finding.dataset.pk}"
    assert str(finding.record) == "cw-1"
    assert str(finding) == "Finding(cw-1, cw-2)"

from uuid import uuid4

import pytest
from django.db import IntegrityError, connection
from django.db.models.query import EmptyQuerySet
from django.test.utils import CaptureQueriesContext
from drf_spectacular.generators import SchemaGenerator
from rest_framework import status
from rest_framework.test import APIClient
from rest_framework.validators import UniqueValidator
from testutils.factories.biographic import (
    BiographicFindingFactory,
    BiographicGroupFactory,
    BiographicRecordFactory,
    BiographicSetFactory,
)

from hope_dedup_engine.apps.biographic.config import get_default_group_settings
from hope_dedup_engine.apps.biographic.const import UPDATE_STATUS_TASK
from hope_dedup_engine.apps.biographic.exceptions import GroupDeleteError
from hope_dedup_engine.apps.biographic.models import (
    BiographicFinding,
    BiographicGroup,
    BiographicJob,
    BiographicRecord,
    BiographicSet,
)
from hope_dedup_engine.apps.biographic.serializers import DUPLICATE_IN_BATCH, MAX_RECORDS_PER_BATCH
from hope_dedup_engine.apps.biographic.services.lifecycle import (
    ANOTHER_SET_ACTIVE,
    LOCK_HELD,
    NO_RECORDS,
    QUEUE_FAILED,
)
from hope_dedup_engine.apps.biographic.views import BiographicFindingsViewSet

pytestmark = pytest.mark.django_db

State = BiographicSet.State
BA, PROGRAM = "afg", "ab12"


def datasets_url(business_area: str = BA, program_code: str = PROGRAM) -> str:
    return f"/api/biographic/{business_area}/{program_code}/datasets/"


def group_url(business_area: str = BA, program_code: str = PROGRAM) -> str:
    return f"/api/biographic/{business_area}/{program_code}/"


def dataset_url(dataset: BiographicSet, action: str = "") -> str:
    group = dataset.group
    suffix = f"{action}/" if action else ""
    return f"{datasets_url(group.business_area, group.program_code)}{dataset.pk}/{suffix}"


def record(reference_pk: str, **payload) -> dict:
    return {"reference_pk": reference_pk, "payload": {"full_name": "Maria Gonzalez", **payload}}


@pytest.fixture
def group() -> BiographicGroup:
    return BiographicGroupFactory(business_area=BA, program_code=PROGRAM, settings=get_default_group_settings())


@pytest.fixture
def pending(group) -> BiographicSet:
    dataset = BiographicSetFactory(group=group)
    BiographicRecordFactory(dataset=dataset)
    return dataset


def in_state(group: BiographicGroup, state: str, *, locked: bool = False) -> BiographicSet:
    dataset = BiographicSetFactory(group=group, state=state)
    if locked:
        BiographicGroup.objects.filter(pk=group.pk).update(processing_locked=True)
    return dataset


def locked(group: BiographicGroup) -> bool:
    group.refresh_from_db()
    return group.processing_locked


# --- create and retrieve ----------------------------------------------------


def test_create_registers_the_program_and_returns_a_pending_set(api: APIClient):
    response = api.post(datasets_url(), format="json")

    assert response.status_code == status.HTTP_201_CREATED
    body = response.json()
    assert body["status"] == "pending"
    assert body["records_count"] == 0
    assert body["error"] is None
    assert (body["notification_url"], body["notify"]) == (None, True)
    group = BiographicGroup.objects.get(business_area=BA, program_code=PROGRAM)
    assert group.settings == get_default_group_settings()
    assert BiographicSet.objects.get(pk=body["dataset_id"]).group == group


def test_create_takes_a_notification_url_and_switch(api: APIClient):
    body = {"notification_url": "https://hope.example.org/callback/42/", "notify": False}

    response = api.post(datasets_url(), body, format="json")

    assert response.status_code == status.HTTP_201_CREATED
    dataset = BiographicSet.objects.get(pk=response.json()["dataset_id"])
    assert (dataset.notification_url, dataset.notify) == (body["notification_url"], False)
    assert response.json()["notification_url"] == body["notification_url"]


def test_create_refuses_a_notification_url_that_is_not_one(api: APIClient):
    response = api.post(datasets_url(), {"notification_url": "not a url"}, format="json")
    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert "notification_url" in response.json()
    assert not BiographicSet.objects.exists()


def test_create_reuses_the_program_and_lowercases_it(api: APIClient, group):
    response = api.post(datasets_url("AFG", "AB12"), format="json")

    assert response.status_code == status.HTTP_201_CREATED
    assert BiographicGroup.objects.count() == 1
    assert group.sets.count() == 1


def test_create_is_allowed_while_another_set_is_active(api: APIClient, group):
    in_state(group, State.DEDUPLICATED, locked=True)
    assert api.post(datasets_url(), format="json").status_code == status.HTTP_201_CREATED


def test_create_takes_the_id_the_client_chose(api: APIClient):
    chosen = uuid4()

    response = api.post(datasets_url(), {"id": str(chosen)}, format="json")

    assert response.status_code == status.HTTP_201_CREATED
    assert response.json()["dataset_id"] == str(chosen)
    assert BiographicSet.objects.get(pk=chosen).state == State.PENDING


def test_create_generates_an_id_when_none_is_sent(api: APIClient):
    response = api.post(datasets_url(), format="json")

    assert response.status_code == status.HTTP_201_CREATED
    assert BiographicSet.objects.filter(pk=response.json()["dataset_id"]).exists()


def test_create_refuses_an_id_already_in_use(api: APIClient, pending):
    response = api.post(datasets_url(), {"id": str(pending.pk)}, format="json")

    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert "id" in response.json()
    assert BiographicSet.objects.count() == 1


def test_an_id_taken_after_validation_is_still_a_400(api: APIClient, pending, mocker):
    """Two requests with the same new id both pass validation; the slower one must not get a 500."""
    mocker.patch.object(UniqueValidator, "__call__", return_value=None)

    response = api.post(datasets_url(), {"id": str(pending.pk)}, format="json")

    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert response.json() == {"id": [str(UniqueValidator.message)]}
    assert BiographicSet.objects.count() == 1


def test_create_locks_the_program_so_a_delete_waits(api: APIClient, group):
    with CaptureQueriesContext(connection) as queries:
        assert api.post(datasets_url(), {}, format="json").status_code == status.HTTP_201_CREATED

    table = BiographicGroup._meta.db_table
    assert any(table in query["sql"] and "FOR UPDATE" in query["sql"] for query in queries)


def test_create_refuses_an_id_used_in_another_program(api: APIClient):
    other = BiographicSetFactory()

    response = api.post(datasets_url(), {"id": str(other.pk)}, format="json")

    assert response.status_code == status.HTTP_400_BAD_REQUEST


def test_create_refuses_an_id_that_is_not_a_uuid(api: APIClient):
    response = api.post(datasets_url(), {"id": "12"}, format="json")

    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert "id" in response.json()
    assert not BiographicSet.objects.exists()


def test_create_in_a_deleted_program_registers_it_again(api: APIClient, group):
    BiographicGroup.objects.filter(pk=group.pk).update(deleted=True)

    response = api.post(datasets_url(), format="json")

    assert response.status_code == status.HTTP_201_CREATED
    revived = BiographicSet.objects.get(pk=response.json()["dataset_id"]).group
    assert revived.pk != group.pk
    assert not revived.deleted
    assert BiographicGroup.objects.filter(business_area=BA, program_code=PROGRAM).count() == 2


def test_listing_sets_is_not_offered(api: APIClient):
    assert api.get(datasets_url()).status_code == status.HTTP_405_METHOD_NOT_ALLOWED


def test_retrieve_reports_state_error_and_record_count(api: APIClient, group):
    dataset = BiographicSetFactory(group=group, state=State.FAILED, error="Elasticsearch unavailable")
    BiographicRecordFactory.create_batch(3, dataset=dataset)

    body = api.get(dataset_url(dataset)).json()

    assert body["dataset_id"] == str(dataset.pk)
    assert body["status"] == "failed"
    assert body["error"] == "Elasticsearch unavailable"
    assert body["records_count"] == 3
    assert (body["batch_duplicates"], body["population_duplicates"]) == (0, 0)


def test_retrieve_counts_records_with_a_duplicate_per_scope(api: APIClient, group):
    """HOPE's counters: people with at least one duplicate, not pairs."""
    dataset = BiographicSetFactory(group=group, state=State.DEDUPLICATED)
    with_two_batch, with_both, clean = BiographicRecordFactory.create_batch(3, dataset=dataset)
    BiographicFindingFactory.create_batch(2, record=with_two_batch, scope=BiographicFinding.Scope.BATCH)
    BiographicFindingFactory(record=with_both, scope=BiographicFinding.Scope.BATCH)
    BiographicFindingFactory(record=with_both, scope=BiographicFinding.Scope.POPULATION)
    # Another set's findings never leak into this one's counts.
    BiographicFindingFactory(record__dataset=BiographicSetFactory(group=group), scope=BiographicFinding.Scope.BATCH)

    body = api.get(dataset_url(dataset)).json()

    assert body["records_count"] == 3
    assert (body["batch_duplicates"], body["population_duplicates"]) == (2, 1)


def test_retrieve_is_scoped_to_the_program(api: APIClient, group):
    dataset = BiographicSetFactory()
    response = api.get(f"{datasets_url()}{dataset.pk}/")
    assert response.status_code == status.HTTP_404_NOT_FOUND


def test_retrieve_hides_deleted_programs(api: APIClient, pending):
    BiographicGroup.objects.filter(pk=pending.group_id).update(deleted=True)
    assert api.get(dataset_url(pending)).status_code == status.HTTP_404_NOT_FOUND


@pytest.mark.parametrize("dataset_id", ["abc", "12"])
def test_ids_that_are_not_uuids_do_not_route(api: APIClient, dataset_id):
    assert api.get(f"{datasets_url()}{dataset_id}/").status_code == status.HTTP_404_NOT_FOUND


def test_unknown_ids_are_not_found(api: APIClient, group):
    assert api.get(f"{datasets_url()}{uuid4()}/").status_code == status.HTTP_404_NOT_FOUND


def test_ids_route_in_either_case(api: APIClient, scored):
    upper = str(scored.pk).upper()

    assert api.get(f"{datasets_url()}{upper}/").json()["dataset_id"] == str(scored.pk)
    assert api.get(f"{datasets_url()}{upper}/findings/").status_code == status.HTTP_200_OK


# --- records ----------------------------------------------------------------


def test_records_are_stored_with_payload_unchanged_and_full_name_copied(api: APIClient, group):
    dataset = BiographicSetFactory(group=group)
    payload = {
        "full_name": "  Maria  Gonzalez ",
        "given_name": "Maria",
        "birth_date": "1990-05-15",
        "phone_no": None,
    }

    response = api.post(
        dataset_url(dataset, "records"), {"records": [{"reference_pk": "cw-1", "payload": payload}]}, format="json"
    )

    assert response.status_code == status.HTTP_201_CREATED
    assert response.json() == {"received": 1, "records_count": 1}
    stored = BiographicRecord.objects.get(dataset=dataset, reference_pk="cw-1")
    assert stored.payload == payload
    assert stored.full_name == "  Maria  Gonzalez "
    assert stored.payload_version == 1


@pytest.mark.parametrize("payload", [{}, {"full_name": None}, {"full_name": ""}, {"given_name": "Maria"}])
def test_a_record_without_a_full_name_is_rejected(api: APIClient, group, payload):
    dataset = BiographicSetFactory(group=group)
    batch = {"records": [{"reference_pk": "cw-1", "payload": payload}]}

    response = api.post(dataset_url(dataset, "records"), batch, format="json")

    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert set(response.json()["records"]["0"]["payload"]) == {"full_name"}
    assert not dataset.records.exists()


def test_unknown_payload_keys_are_dropped(api: APIClient, group):
    dataset = BiographicSetFactory(group=group)
    batch = {"records": [record("cw-1", identities=[{"number": "1", "partner": "UNHCR"}])]}

    assert api.post(dataset_url(dataset, "records"), batch, format="json").status_code == status.HTTP_201_CREATED
    assert BiographicRecord.objects.get(reference_pk="cw-1").payload == {"full_name": "Maria Gonzalez"}


def test_batches_accumulate_and_a_resent_record_replaces_the_old_one(api: APIClient, group):
    dataset = BiographicSetFactory(group=group)
    url = dataset_url(dataset, "records")

    api.post(url, {"records": [record("cw-1"), record("cw-2")]}, format="json")
    response = api.post(url, {"records": [record("cw-2", full_name="Mario Gonzalez"), record("cw-3")]}, format="json")

    assert response.json() == {"received": 2, "records_count": 3}
    assert dataset.records.get(reference_pk="cw-2").full_name == "Mario Gonzalez"


def test_a_repeated_reference_pk_in_one_batch_points_at_the_offender(api: APIClient, group):
    dataset = BiographicSetFactory(group=group)
    batch = {"records": [record("cw-1"), record("cw-2"), record("cw-1")]}

    response = api.post(dataset_url(dataset, "records"), batch, format="json")

    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert response.json() == {"records": {"2": {"reference_pk": [DUPLICATE_IN_BATCH]}}}
    assert not dataset.records.exists()


def test_an_invalid_record_points_at_its_index_and_field_and_nothing_is_stored(api: APIClient, group):
    dataset = BiographicSetFactory(group=group)
    batch = {"records": [record("cw-1"), record("cw-2", birth_date="15/05/1990")]}

    response = api.post(dataset_url(dataset, "records"), batch, format="json")

    assert response.status_code == status.HTTP_400_BAD_REQUEST
    errors = response.json()["records"]
    assert set(errors) == {"1"}
    assert set(errors["1"]["payload"]) == {"birth_date"}
    assert not dataset.records.exists()


@pytest.mark.parametrize(
    "body",
    [
        {},
        {"records": []},
        {"records": "cw-1"},
        {"records": [{"payload": {}}]},
        {"records": [{"reference_pk": "", "payload": {}}]},
        {"records": [{"reference_pk": "x" * 101, "payload": {}}]},
        {"records": [{"reference_pk": "cw-1"}]},
    ],
)
def test_malformed_batches_are_rejected(api: APIClient, group, body):
    dataset = BiographicSetFactory(group=group)
    assert api.post(dataset_url(dataset, "records"), body, format="json").status_code == status.HTTP_400_BAD_REQUEST


def test_a_batch_has_a_size_limit(api: APIClient, group):
    dataset = BiographicSetFactory(group=group)
    batch = {"records": [record(f"cw-{n}") for n in range(MAX_RECORDS_PER_BATCH + 1)]}

    response = api.post(dataset_url(dataset, "records"), batch, format="json")

    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert "records" in response.json()
    assert not dataset.records.exists()


@pytest.mark.parametrize("state", [s for s in State if s != State.PENDING])
def test_records_can_only_be_added_while_pending(api: APIClient, group, state):
    dataset = BiographicSetFactory(group=group, state=state)
    response = api.post(dataset_url(dataset, "records"), {"records": [record("cw-1")]}, format="json")
    assert response.status_code == status.HTTP_409_CONFLICT
    assert not dataset.records.exists()


# --- process ----------------------------------------------------------------


def test_process_starts_indexing_takes_the_lock_and_queues_a_job(api: APIClient, pending, queued_jobs):
    response = api.post(dataset_url(pending, "process"), format="json")

    assert response.status_code == status.HTTP_200_OK
    assert response.json()["status"] == "indexing"
    pending.refresh_from_db()
    assert pending.state == State.INDEXING
    assert locked(pending.group)
    job = BiographicJob.objects.get(dataset=pending)
    assert job.config_overrides == {}
    queued_jobs.assert_called_once_with(job)


def test_process_passes_validated_overrides_to_the_run(api: APIClient, pending, queued_jobs):
    api.post(dataset_url(pending, "process"), {"duplicate_score": 11, "max_hits": 20}, format="json")
    job = BiographicJob.objects.get(dataset=pending)
    assert job.config_overrides == {"duplicate_score": 11.0, "max_hits": 20}


def test_invalid_overrides_are_rejected_before_anything_changes(api: APIClient, pending, queued_jobs):
    response = api.post(dataset_url(pending, "process"), {"duplicate_scor": 11}, format="json")

    assert response.status_code == status.HTTP_400_BAD_REQUEST
    pending.refresh_from_db()
    assert pending.state == State.PENDING
    assert not locked(pending.group)
    assert not BiographicJob.objects.exists()
    queued_jobs.assert_not_called()


def test_a_failed_set_can_be_retried(api: APIClient, group, queued_jobs):
    dataset = BiographicSetFactory(group=group, state=State.FAILED, error="boom")
    BiographicRecordFactory(dataset=dataset)

    response = api.post(dataset_url(dataset, "process"), format="json")

    assert response.status_code == status.HTTP_200_OK
    dataset.refresh_from_db()
    assert dataset.state == State.INDEXING
    assert dataset.error is None


@pytest.mark.parametrize("state", [s for s in State if s not in BiographicSet.PROCESSABLE_STATES])
def test_process_refuses_sets_that_are_not_pending_or_failed(api: APIClient, group, state, queued_jobs):
    dataset = BiographicSetFactory(group=group, state=state)
    BiographicRecordFactory(dataset=dataset)
    assert api.post(dataset_url(dataset, "process"), format="json").status_code == status.HTTP_409_CONFLICT
    queued_jobs.assert_not_called()


def test_process_refuses_an_empty_set(api: APIClient, group, queued_jobs):
    dataset = BiographicSetFactory(group=group)
    response = api.post(dataset_url(dataset, "process"), format="json")
    assert response.status_code == status.HTTP_409_CONFLICT
    assert response.json()["detail"] == NO_RECORDS


@pytest.mark.parametrize("active", BiographicSet.ACTIVE_STATES)
def test_process_refuses_while_another_set_in_the_program_is_active(api: APIClient, pending, active, queued_jobs):
    in_state(pending.group, active, locked=True)

    response = api.post(dataset_url(pending, "process"), format="json")

    assert response.status_code == status.HTTP_409_CONFLICT
    assert response.json()["detail"] == ANOTHER_SET_ACTIVE
    queued_jobs.assert_not_called()


def test_process_ignores_other_sets_that_are_only_queued(api: APIClient, pending, queued_jobs):
    BiographicRecordFactory(dataset=BiographicSetFactory(group=pending.group, state=State.PENDING))
    BiographicSetFactory(group=pending.group, state=State.FAILED)
    assert api.post(dataset_url(pending, "process"), format="json").status_code == status.HTTP_200_OK


def test_two_programs_in_one_business_area_process_side_by_side(api: APIClient, pending, queued_jobs):
    other = BiographicSetFactory(group__business_area=BA, group__program_code="cd34")
    BiographicRecordFactory(dataset=other)

    assert api.post(dataset_url(pending, "process"), format="json").status_code == status.HTTP_200_OK
    assert api.post(dataset_url(other, "process"), format="json").status_code == status.HTTP_200_OK


def test_a_second_process_call_is_a_conflict(api: APIClient, pending, queued_jobs):
    api.post(dataset_url(pending, "process"), format="json")
    assert api.post(dataset_url(pending, "process"), format="json").status_code == status.HTTP_409_CONFLICT
    assert queued_jobs.call_count == 1


def test_a_stale_lock_blocks_processing(api: APIClient, pending, queued_jobs):
    BiographicGroup.objects.filter(pk=pending.group_id).update(processing_locked=True)

    response = api.post(dataset_url(pending, "process"), format="json")

    assert response.status_code == status.HTTP_409_CONFLICT
    assert response.json()["detail"] == LOCK_HELD


def test_losing_the_race_for_the_slot_releases_the_lock(api: APIClient, pending, queued_jobs, mocker):
    mocker.patch.object(BiographicSet, "set_state", side_effect=IntegrityError)

    response = api.post(dataset_url(pending, "process"), format="json")

    assert response.status_code == status.HTTP_409_CONFLICT
    assert response.json()["detail"] == ANOTHER_SET_ACTIVE
    assert not locked(pending.group)
    queued_jobs.assert_not_called()


def test_an_unexpected_error_while_starting_releases_the_lock(api: APIClient, pending, queued_jobs, mocker):
    mocker.patch.object(BiographicSet, "set_state", side_effect=RuntimeError("database went away"))

    with pytest.raises(RuntimeError):
        api.post(dataset_url(pending, "process"), format="json")
    assert not locked(pending.group)


def test_a_queue_failure_marks_the_set_failed_and_releases_the_lock(api: APIClient, pending, queued_jobs):
    queued_jobs.side_effect = ConnectionError("broker down")

    with pytest.raises(ConnectionError):
        api.post(dataset_url(pending, "process"), format="json")

    pending.refresh_from_db()
    assert pending.state == State.FAILED
    assert pending.error == QUEUE_FAILED
    assert not locked(pending.group)


# --- cancel, approve, reject -----------------------------------------------


def test_cancel_a_pending_set_touches_nothing_else(api: APIClient, pending, queued_tasks):
    response = api.post(dataset_url(pending, "cancel"), format="json")

    assert response.status_code == status.HTTP_200_OK
    assert response.json()["status"] == "canceled"
    queued_tasks.assert_not_called()


def test_cancel_a_failed_set_cleans_up_what_it_may_have_indexed(api: APIClient, group, queued_tasks):
    dataset = BiographicSetFactory(group=group, state=State.FAILED)
    assert api.post(dataset_url(dataset, "cancel"), format="json").status_code == status.HTTP_200_OK
    dataset.refresh_from_db()
    assert dataset.search_sync_pending
    queued_tasks.assert_called_once_with(UPDATE_STATUS_TASK, args=[str(dataset.pk)], kwargs={})


@pytest.mark.parametrize("state", [s for s in State if s not in BiographicSet.CANCELABLE_STATES])
def test_cancel_refuses_sets_in_flight_or_decided(api: APIClient, group, state, queued_tasks):
    dataset = BiographicSetFactory(group=group, state=state)
    assert api.post(dataset_url(dataset, "cancel"), format="json").status_code == status.HTTP_409_CONFLICT
    dataset.refresh_from_db()
    assert dataset.state == state


@pytest.mark.parametrize(("action", "outcome"), [("approve", State.APPROVED), ("reject", State.REJECTED)])
def test_a_decision_flags_the_sync_and_queues_the_status_update(api: APIClient, group, queued_tasks, action, outcome):
    dataset = in_state(group, State.DEDUPLICATED)

    response = api.post(dataset_url(dataset, action), format="json")

    assert response.status_code == status.HTTP_200_OK
    assert response.json()["status"] == outcome
    dataset.refresh_from_db()
    assert dataset.search_sync_pending
    queued_tasks.assert_called_once_with(UPDATE_STATUS_TASK, args=[str(dataset.pk)], kwargs={})


@pytest.mark.parametrize("action", ["approve", "reject"])
def test_a_decision_leaves_the_program_lock_alone(api: APIClient, group, queued_tasks, action):
    # The task releases the lock when it finishes; a decision never touches it.
    dataset = in_state(group, State.DEDUPLICATED, locked=True)
    api.post(dataset_url(dataset, action), format="json")
    assert locked(group)


@pytest.mark.parametrize("action", ["approve", "reject"])
@pytest.mark.parametrize("state", [s for s in State if s != State.DEDUPLICATED])
def test_a_decision_needs_a_deduplicated_set(api: APIClient, group, queued_tasks, action, state):
    dataset = in_state(group, state)

    assert api.post(dataset_url(dataset, action), format="json").status_code == status.HTTP_409_CONFLICT
    dataset.refresh_from_db()
    assert not dataset.search_sync_pending
    queued_tasks.assert_not_called()


@pytest.mark.parametrize(
    "case",
    [
        (State.DEDUPLICATED, "approve", State.APPROVED),
        (State.DEDUPLICATED, "reject", State.REJECTED),
        (State.FAILED, "cancel", State.CANCELED),
    ],
)
def test_a_decision_stands_when_its_status_update_cannot_be_queued(api: APIClient, group, queued_tasks, mocker, case):
    start, action, outcome = case
    dataset = in_state(group, start)
    queued_tasks.side_effect = ConnectionError("broker down")
    logger = mocker.patch("hope_dedup_engine.apps.biographic.services.lifecycle.logger")

    response = api.post(dataset_url(dataset, action), format="json")

    assert response.status_code == status.HTTP_200_OK
    assert response.json()["status"] == outcome
    dataset.refresh_from_db()
    # Still flagged: the next run in the program reconciles it.
    assert dataset.search_sync_pending
    logger.exception.assert_called_once_with("Could not queue the status update for biographic set %s", dataset.pk)


def test_reject_after_approve_is_a_conflict(api: APIClient, group, queued_tasks):
    dataset = in_state(group, State.DEDUPLICATED)
    api.post(dataset_url(dataset, "approve"), format="json")
    assert api.post(dataset_url(dataset, "reject"), format="json").status_code == status.HTTP_409_CONFLICT


def test_after_approval_the_next_set_can_be_processed(api: APIClient, group, queued_tasks, queued_jobs):
    first = in_state(group, State.DEDUPLICATED)
    second = BiographicSetFactory(group=group)
    BiographicRecordFactory(dataset=second)

    assert api.post(dataset_url(second, "process"), format="json").status_code == status.HTTP_409_CONFLICT
    api.post(dataset_url(first, "approve"), format="json")
    assert api.post(dataset_url(second, "process"), format="json").status_code == status.HTTP_200_OK


# --- findings ---------------------------------------------------------------


def findings_url(dataset: BiographicSet) -> str:
    return f"{dataset_url(dataset)}findings/"


@pytest.mark.parametrize("state", [s for s in State if s not in BiographicSet.FINDINGS_STATES])
def test_findings_are_refused_until_deduplicated(api: APIClient, group, state):
    dataset = BiographicSetFactory(group=group, state=state)
    assert api.get(findings_url(dataset)).status_code == status.HTTP_409_CONFLICT


@pytest.mark.parametrize("state", BiographicSet.FINDINGS_STATES)
def test_findings_have_the_documented_shape(api: APIClient, group, state):
    dataset = BiographicSetFactory(group=group, state=state)
    BiographicFindingFactory(
        record__dataset=dataset,
        record__reference_pk="cw-1",
        matched_reference_pk="cw-9",
        matched_full_name="Maria Gonzales",
        matched_birth_date="1990-05-15",
        score=14.0,
        proximity_to_score=8.0,
        scope=BiographicFinding.Scope.POPULATION,
    )

    body = api.get(findings_url(dataset)).json()

    assert body["count"] == 1
    assert body["results"] == [
        {
            "reference_pk": "cw-1",
            "matched_reference_pk": "cw-9",
            "scope": "population",
            "score": 14.0,
            "proximity_to_score": 8.0,
            "matched_full_name": "Maria Gonzales",
            "matched_birth_date": "1990-05-15",
        }
    ]


@pytest.fixture
def scored(group) -> BiographicSet:
    dataset = BiographicSetFactory(group=group, state=State.DEDUPLICATED)
    first = BiographicRecordFactory(dataset=dataset, reference_pk="cw-1")
    second = BiographicRecordFactory(dataset=dataset, reference_pk="cw-2")
    BiographicFindingFactory(record=first, matched_reference_pk="cw-2", score=9.0, scope=BiographicFinding.Scope.BATCH)
    BiographicFindingFactory(record=second, matched_reference_pk="cw-1", score=9.0, scope=BiographicFinding.Scope.BATCH)
    BiographicFindingFactory(record=first, matched_reference_pk="old-7", score=14.0)
    BiographicFindingFactory(record=second, matched_reference_pk="old-8", score=6.5)
    BiographicFindingFactory(record__dataset=BiographicSetFactory(group=group, state=State.APPROVED))
    return dataset


def matches(response) -> list[tuple[str, str]]:
    return [(row["reference_pk"], row["matched_reference_pk"]) for row in response.json()["results"]]


def test_findings_are_best_first_and_scoped_to_the_set(api: APIClient, scored):
    assert matches(api.get(findings_url(scored))) == [
        ("cw-1", "old-7"),
        ("cw-2", "cw-1"),
        ("cw-1", "cw-2"),
        ("cw-2", "old-8"),
    ]


def test_findings_filter_by_min_score(api: APIClient, scored):
    assert len(matches(api.get(findings_url(scored), {"min_score": 9}))) == 3
    assert matches(api.get(findings_url(scored), {"min_score": 10})) == [("cw-1", "old-7")]


def test_findings_filter_by_scope(api: APIClient, scored):
    assert set(matches(api.get(findings_url(scored), {"scope": "batch"}))) == {("cw-1", "cw-2"), ("cw-2", "cw-1")}
    assert api.get(findings_url(scored), {"scope": "nowhere"}).status_code == status.HTTP_400_BAD_REQUEST


def test_findings_filter_by_reference_pk(api: APIClient, scored):
    assert matches(api.get(findings_url(scored), {"reference_pk": "cw-2"})) == [("cw-2", "cw-1"), ("cw-2", "old-8")]


def test_findings_are_paginated(api: APIClient, scored):
    body = api.get(findings_url(scored), {"page_size": 3}).json()
    assert body["count"] == 4
    assert len(body["results"]) == 3
    assert body["next"]


def test_findings_of_another_program_are_not_found(api: APIClient, scored):
    other = BiographicSetFactory(state=State.DEDUPLICATED)
    assert api.get(f"{datasets_url()}{other.pk}/findings/").status_code == status.HTTP_404_NOT_FOUND


# --- delete the program -----------------------------------------------------


def test_delete_soft_deletes_the_program(api: APIClient, pending):
    response = api.delete(group_url())

    assert response.status_code == status.HTTP_204_NO_CONTENT
    group = pending.group
    group.refresh_from_db()
    assert group.deleted
    assert BiographicSet.objects.filter(pk=pending.pk).exists()


def test_delete_hides_the_programs_sets(api: APIClient, pending):
    api.delete(group_url())

    assert api.get(dataset_url(pending)).status_code == status.HTTP_404_NOT_FOUND


def test_delete_is_lowercased_like_every_other_route(api: APIClient, group):
    assert api.delete(group_url("AFG", "AB12")).status_code == status.HTTP_204_NO_CONTENT
    group.refresh_from_db()
    assert group.deleted


def test_delete_is_idempotent(api: APIClient, group):
    assert api.delete(group_url()).status_code == status.HTTP_204_NO_CONTENT
    assert api.delete(group_url()).status_code == status.HTTP_204_NO_CONTENT


def test_delete_of_an_unknown_program_is_a_no_op(api: APIClient):
    assert api.delete(group_url()).status_code == status.HTTP_204_NO_CONTENT
    assert not BiographicGroup.objects.exists()


def test_delete_leaves_other_programs_alone(api: APIClient, group):
    other = BiographicGroupFactory(business_area=BA, program_code="cd34")

    api.delete(group_url())

    other.refresh_from_db()
    assert not other.deleted


def test_delete_is_refused_while_a_task_is_running(api: APIClient, group):
    BiographicGroup.objects.filter(pk=group.pk).update(processing_locked=True)

    response = api.delete(group_url())

    assert response.status_code == status.HTTP_409_CONFLICT
    assert response.json()["detail"] == GroupDeleteError.message
    group.refresh_from_db()
    assert not group.deleted


def test_delete_only_accepts_delete(api: APIClient, group):
    assert api.get(group_url()).status_code == status.HTTP_405_METHOD_NOT_ALLOWED
    assert api.post(group_url()).status_code == status.HTTP_405_METHOD_NOT_ALLOWED


# --- auth -------------------------------------------------------------------

SOME_SET = "7d5ea5f1-4b6a-4a8c-9c3e-0f5f8f4b2c11"

ENDPOINTS = [
    ("post", ""),
    ("get", f"{SOME_SET}/"),
    ("post", f"{SOME_SET}/records/"),
    ("post", f"{SOME_SET}/process/"),
    ("post", f"{SOME_SET}/cancel/"),
    ("post", f"{SOME_SET}/approve/"),
    ("post", f"{SOME_SET}/reject/"),
    ("get", f"{SOME_SET}/findings/"),
]


@pytest.mark.parametrize(("method", "path"), ENDPOINTS)
def test_every_endpoint_needs_a_token(method, path):
    response = getattr(APIClient(), method)(f"{datasets_url()}{path}")
    assert response.status_code == status.HTTP_401_UNAUTHORIZED


@pytest.mark.parametrize(("method", "path"), ENDPOINTS)
def test_an_invalid_token_is_refused(method, path):
    client = APIClient()
    client.credentials(HTTP_AUTHORIZATION="Token not-a-real-token")
    assert getattr(client, method)(f"{datasets_url()}{path}").status_code == status.HTTP_401_UNAUTHORIZED


@pytest.mark.parametrize(("method", "path"), ENDPOINTS)
def test_every_endpoint_needs_the_biographic_grant(api_without_grant: APIClient, method, path):
    response = getattr(api_without_grant, method)(f"{datasets_url()}{path}")
    assert response.status_code == status.HTTP_403_FORBIDDEN
    assert not BiographicGroup.objects.exists()


def test_every_endpoint_is_grouped_under_biographic_in_the_schema():
    schema = SchemaGenerator().get_schema(request=None, public=True)
    operations = [
        operation
        for path, methods in schema["paths"].items()
        if path.startswith("/api/biographic/")
        for operation in methods.values()
    ]
    assert len(operations) == len(ENDPOINTS) + 1  # the program's own DELETE
    assert all(operation["tags"] == ["biographic"] for operation in operations)


def test_the_findings_path_documents_its_dataset_id_as_a_uuid():
    schema = SchemaGenerator().get_schema(request=None, public=True)
    (operation,) = [
        methods["get"] for path, methods in schema["paths"].items() if path.endswith("/{dataset_id}/findings/")
    ]
    (parameter,) = [p for p in operation["parameters"] if p["name"] == "dataset_id"]
    assert parameter["schema"] == {"type": "string", "format": "uuid"}


def test_deleting_a_program_needs_a_token():
    assert APIClient().delete(group_url()).status_code == status.HTTP_401_UNAUTHORIZED


def test_deleting_a_program_needs_the_biographic_grant(api_without_grant: APIClient, group):
    assert api_without_grant.delete(group_url()).status_code == status.HTTP_403_FORBIDDEN
    group.refresh_from_db()
    assert not group.deleted


def test_findings_queryset_is_empty_for_schema_generation():
    view = BiographicFindingsViewSet(swagger_fake_view=True, kwargs={})
    assert isinstance(view.get_queryset(), EmptyQuerySet)

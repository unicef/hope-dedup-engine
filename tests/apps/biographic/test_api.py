from datetime import timedelta

import pytest
from django.db import IntegrityError
from django.utils import timezone
from rest_framework import status
from rest_framework.reverse import reverse
from rest_framework.test import APIClient

from hope_dedup_engine.apps.api.grant import Grant
from hope_dedup_engine.apps.biographic.contracts import (
    BIRTH_DATE_FIELD,
    FULL_NAME_FIELD,
    IDENTITIES_FIELD,
    PAYLOAD_FIELDS,
)
from hope_dedup_engine.apps.biographic.models import BiographicFinding, BiographicGroup, BiographicRecord, BiographicSet
from testutils.factories.auth import APITokenFactory
from testutils.factories.biographic import (
    BiographicFindingFactory,
    BiographicGroupFactory,
    BiographicRecordFactory,
    BiographicSetFactory,
)
from testutils.factories.user import UserFactory

from api.utils import create_api_client

pytestmark = pytest.mark.django_db

INDEX_TASK = "apps.biographic.tasks.index_biographic_records"
PROCESS_TASK = "apps.biographic.tasks.process_biographic_dataset"
STATUS_TASK = "apps.biographic.tasks.update_biographic_status"


def datasets_url(business_area: str = "afghanistan", program_id: str = "prog-1") -> str:
    return reverse(
        "biographic-datasets",
        kwargs={"business_area_slug": business_area, "program_id": program_id},
    )


def action_url(name: str, dataset_id: int, business_area: str = "afghanistan", program_id: str = "prog-1") -> str:
    return reverse(
        name,
        kwargs={
            "business_area_slug": business_area,
            "program_id": program_id,
            "dataset_id": dataset_id,
        },
    )


def person(reference_pk: str = "cw-123", **extra: object) -> dict[str, object]:
    body: dict[str, object] = {
        "reference_pk": reference_pk,
        "given_name": "Maria",
        "family_name": "Gonzalez",
        "full_name": "Maria Gonzalez",
        "birth_date": "1990-05-15",
    }
    body.update(extra)
    return body


def test_create_returns_pending_and_queues_indexing(biographic_client: APIClient, queued_tasks) -> None:
    response = biographic_client.post(datasets_url(), {"records": [person()]}, format="json")

    assert response.status_code == status.HTTP_201_CREATED
    body = response.json()
    assert set(body) == {"dataset_id", "status"}
    assert body["status"] == "pending"
    dataset = BiographicSet.objects.get(pk=body["dataset_id"])
    assert dataset.state == BiographicSet.State.PENDING
    record = dataset.records.get()
    assert record.reference_pk == "cw-123"
    assert record.full_name == "Maria Gonzalez"
    assert record.payload["birth_date"] == "1990-05-15"
    queued_tasks.assert_called_once_with(INDEX_TASK, args=[dataset.pk], kwargs={})


def test_create_while_another_set_is_pending_is_allowed(biographic_client: APIClient, queued_tasks) -> None:
    first = biographic_client.post(datasets_url(), {"records": [person("cw-1")]}, format="json")
    second = biographic_client.post(datasets_url(), {"records": [person("cw-2")]}, format="json")

    assert first.status_code == status.HTTP_201_CREATED
    assert second.status_code == status.HTTP_201_CREATED
    assert BiographicSet.objects.filter(group__program_id="prog-1").count() == 2
    assert queued_tasks.call_count == 2


def test_valid_payload_round_trips_every_contract_field(biographic_client: APIClient, queued_tasks) -> None:
    payload: dict[str, object] = {"reference_pk": "cw-123"}
    for name in PAYLOAD_FIELDS:
        if name == BIRTH_DATE_FIELD:
            payload[name] = "1990-05-15T00:00:00Z"
        elif name == IDENTITIES_FIELD:
            payload[name] = [{"number": "A123", "partner": "UNHCR"}]
        elif name == FULL_NAME_FIELD:
            payload[name] = "Maria Gonzalez"
        else:
            payload[name] = name

    response = biographic_client.post(datasets_url(), {"records": [payload]}, format="json")
    assert response.status_code == status.HTTP_201_CREATED
    record = BiographicRecord.objects.get(dataset_id=response.json()["dataset_id"])
    stored = {"reference_pk": record.reference_pk, **record.payload}
    assert stored == payload
    assert record.full_name == "Maria Gonzalez"


@pytest.mark.parametrize(
    ("record", "field"),
    [
        (person(birth_date="15/05/1990"), "birth_date"),
        (person(birth_date="not-a-date"), "birth_date"),
        (person(birth_date=19900515), "birth_date"),
        (person(unicef_id="U1"), "unicef_id"),
        (person(identities="A123"), "identities"),
        (person(identities=[{"number": 1, "partner": "UNHCR"}]), "identities"),
        (person(identities=[{"number": "A123"}]), "identities"),
        (person(identities=[{"partner": "UNHCR", "number": "A123", "country": "AF"}]), "identities"),
    ],
)
def test_invalid_record_returns_400_with_index_and_field(
    biographic_client: APIClient,
    queued_tasks,
    record: dict[str, object],
    field: str,
) -> None:
    response = biographic_client.post(
        datasets_url(),
        {"records": [person("cw-ok"), record]},
        format="json",
    )

    assert response.status_code == status.HTTP_400_BAD_REQUEST
    errors = response.json()["errors"]
    assert errors[0]["index"] == 1
    assert errors[0]["field"] == field
    assert BiographicSet.objects.count() == 0
    queued_tasks.assert_not_called()


def test_duplicate_reference_pk_in_one_request_is_400(biographic_client: APIClient, queued_tasks) -> None:
    response = biographic_client.post(
        datasets_url(),
        {"records": [person("cw-1"), person("cw-1")]},
        format="json",
    )
    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert response.json()["errors"][0]["field"] == "reference_pk"
    assert BiographicSet.objects.count() == 0


def test_oversized_program_id_is_400(biographic_client: APIClient) -> None:
    response = biographic_client.post(datasets_url(program_id="p" * 101), {"records": [person()]}, format="json")
    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert BiographicGroup.objects.count() == 0


def test_process_queues_task_and_second_call_in_the_same_group_is_409(
    biographic_client: APIClient,
    queued_tasks,
) -> None:
    created = biographic_client.post(datasets_url(), {"records": [person()]}, format="json")
    dataset_id = created.json()["dataset_id"]
    queued_tasks.reset_mock()

    first = biographic_client.post(action_url("biographic-dataset-process", dataset_id))
    second = biographic_client.post(action_url("biographic-dataset-process", dataset_id))

    assert first.status_code == status.HTTP_200_OK
    assert second.status_code == status.HTTP_409_CONFLICT
    queued_tasks.assert_called_once_with(PROCESS_TASK, args=[dataset_id], kwargs={})
    group = BiographicSet.objects.get(pk=dataset_id).group
    group.refresh_from_db()
    assert group.processing_locked is True


def test_process_is_409_when_another_set_in_the_group_is_pending(biographic_client: APIClient, queued_tasks) -> None:
    first = biographic_client.post(datasets_url(), {"records": [person("cw-1")]}, format="json")
    biographic_client.post(datasets_url(), {"records": [person("cw-2")]}, format="json")
    queued_tasks.reset_mock()

    response = biographic_client.post(action_url("biographic-dataset-process", first.json()["dataset_id"]))

    assert response.status_code == status.HTTP_409_CONFLICT
    queued_tasks.assert_not_called()
    assert BiographicGroup.objects.get(program_id="prog-1").processing_locked is False


def test_two_programs_in_one_business_area_can_process_together(biographic_client: APIClient, queued_tasks) -> None:
    first = biographic_client.post(
        datasets_url(program_id="one"),
        {"records": [person("cw-1")]},
        format="json",
    )
    second = biographic_client.post(
        datasets_url(program_id="two"),
        {"records": [person("cw-2")]},
        format="json",
    )
    queued_tasks.reset_mock()

    first_process = biographic_client.post(
        action_url("biographic-dataset-process", first.json()["dataset_id"], program_id="one"),
    )
    second_process = biographic_client.post(
        action_url("biographic-dataset-process", second.json()["dataset_id"], program_id="two"),
    )

    assert first_process.status_code == status.HTTP_200_OK
    assert second_process.status_code == status.HTTP_200_OK
    assert BiographicGroup.objects.get(program_id="one").processing_locked is True
    assert BiographicGroup.objects.get(program_id="two").processing_locked is True


def test_process_passes_request_config_overrides(biographic_client: APIClient, queued_tasks) -> None:
    created = biographic_client.post(datasets_url(), {"records": [person()]}, format="json")
    queued_tasks.reset_mock()

    response = biographic_client.post(
        action_url("biographic-dataset-process", created.json()["dataset_id"]),
        {"config": {"max_hits": 3}},
        format="json",
    )

    assert response.status_code == status.HTTP_200_OK
    queued_tasks.assert_called_once_with(
        PROCESS_TASK,
        args=[created.json()["dataset_id"]],
        kwargs={"config_overrides": {"max_hits": 3}},
    )


def test_process_rejects_unknown_config_without_locking(biographic_client: APIClient, queued_tasks) -> None:
    created = biographic_client.post(datasets_url(), {"records": [person()]}, format="json")
    queued_tasks.reset_mock()

    response = biographic_client.post(
        action_url("biographic-dataset-process", created.json()["dataset_id"]),
        {"config": {"not_a_setting": 1}},
        format="json",
    )

    assert response.status_code == status.HTTP_400_BAD_REQUEST
    queued_tasks.assert_not_called()
    assert BiographicGroup.objects.get().processing_locked is False


def test_process_wrong_program_is_404(biographic_client: APIClient, queued_tasks) -> None:
    created = biographic_client.post(datasets_url(program_id="one"), {"records": [person()]}, format="json")
    response = biographic_client.post(
        action_url("biographic-dataset-process", created.json()["dataset_id"], program_id="two"),
    )
    assert response.status_code == status.HTTP_404_NOT_FOUND


def test_queue_failure_releases_the_lock(biographic_client: APIClient, queued_tasks) -> None:
    created = biographic_client.post(datasets_url(), {"records": [person()]}, format="json")
    queued_tasks.reset_mock()
    queued_tasks.side_effect = RuntimeError("broker down")
    biographic_client.raise_request_exception = False

    response = biographic_client.post(action_url("biographic-dataset-process", created.json()["dataset_id"]))

    assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR
    assert BiographicGroup.objects.get().processing_locked is False


@pytest.mark.parametrize("state", [BiographicSet.State.PENDING, BiographicSet.State.DEDUPLICATING, "rejected"])
def test_findings_are_rejected_until_deduplicated_or_approved(biographic_client: APIClient, state: str) -> None:
    dataset = BiographicSetFactory(
        group=BiographicGroupFactory(business_area="afghanistan", program_id="prog-1"),
        state=state,
    )
    response = biographic_client.get(action_url("biographic-dataset-findings", dataset.pk))
    assert response.status_code == status.HTTP_409_CONFLICT


@pytest.mark.parametrize("state", [BiographicSet.State.DEDUPLICATED, BiographicSet.State.APPROVED])
def test_findings_match_the_biometric_shape(biographic_client: APIClient, state: str) -> None:
    dataset = _dataset_with_findings(state)
    response = biographic_client.get(action_url("biographic-dataset-findings", dataset.pk))

    assert response.status_code == status.HTTP_200_OK
    body = next(row for row in response.json()["results"] if row["second"]["reference_pk"] == "cw-456")
    assert body["first"] == {"reference_pk": "cw-123"}
    assert body["second"] == {"reference_pk": "cw-456"}
    assert body["score"] == 8.2
    assert body["status_code"] == "duplicate"
    assert body["config"] == {"duplicate_score": 6.0}
    assert body["proximity_to_score"] == 2.2
    assert body["updated_at"]


def test_findings_filter_by_status_code_and_updated_at(biographic_client: APIClient) -> None:
    dataset = _dataset_with_findings(BiographicSet.State.DEDUPLICATED)
    older = BiographicFinding.objects.get(matched_reference_pk="cw-789")
    BiographicFinding.objects.filter(pk=older.pk).update(updated_at=timezone.now() - timedelta(days=2))
    url = action_url("biographic-dataset-findings", dataset.pk)
    cutoff = (timezone.now() - timedelta(hours=1)).isoformat()

    by_status = biographic_client.get(url, {"status_code": "duplicate"})
    by_after = biographic_client.get(url, {"updated_after": cutoff})

    assert {row["second"]["reference_pk"] for row in by_status.json()["results"]} == {"cw-456", "cw-789"}
    assert [row["second"]["reference_pk"] for row in by_after.json()["results"]] == ["cw-456"]


@pytest.mark.parametrize(
    ("params", "detail"),
    [
        ({"status_code": "possible_duplicate"}, "status_code"),
        ({"updated_after": "yesterday"}, "updated_after"),
        ({"updated_before": "not-a-date"}, "updated_before"),
    ],
)
def test_findings_reject_invalid_filters(biographic_client: APIClient, params: dict[str, str], detail: str) -> None:
    dataset = _dataset_with_findings(BiographicSet.State.APPROVED)
    response = biographic_client.get(action_url("biographic-dataset-findings", dataset.pk), params)
    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert detail in response.json()["detail"]


def test_approve_releases_the_lock_and_queues_status_update(biographic_client: APIClient, queued_tasks) -> None:
    dataset = _locked_dataset(BiographicSet.State.DEDUPLICATED)

    response = biographic_client.post(action_url("biographic-dataset-approve", dataset.pk))

    assert response.status_code == status.HTTP_200_OK
    dataset.refresh_from_db()
    dataset.group.refresh_from_db()
    assert dataset.state == BiographicSet.State.APPROVED
    assert dataset.group.processing_locked is False
    queued_tasks.assert_called_once_with(STATUS_TASK, args=[dataset.pk, "approved"], kwargs={})


def test_reject_releases_the_lock_and_queues_status_update(biographic_client: APIClient, queued_tasks) -> None:
    dataset = _locked_dataset(BiographicSet.State.DEDUPLICATED)

    response = biographic_client.post(action_url("biographic-dataset-reject", dataset.pk))

    assert response.status_code == status.HTTP_200_OK
    dataset.refresh_from_db()
    dataset.group.refresh_from_db()
    assert dataset.state == BiographicSet.State.REJECTED
    assert dataset.group.processing_locked is False
    queued_tasks.assert_called_once_with(STATUS_TASK, args=[dataset.pk, "rejected"], kwargs={})


def test_reject_after_approve_is_409(biographic_client: APIClient, queued_tasks) -> None:
    dataset = _locked_dataset(BiographicSet.State.DEDUPLICATED)
    assert biographic_client.post(action_url("biographic-dataset-approve", dataset.pk)).status_code == 200
    queued_tasks.reset_mock()

    response = biographic_client.post(action_url("biographic-dataset-reject", dataset.pk))

    assert response.status_code == status.HTTP_409_CONFLICT
    dataset.refresh_from_db()
    assert dataset.state == BiographicSet.State.APPROVED
    queued_tasks.assert_not_called()


def test_approve_from_pending_is_409_and_keeps_the_lock(biographic_client: APIClient, queued_tasks) -> None:
    created = biographic_client.post(datasets_url(), {"records": [person()]}, format="json")
    dataset_id = created.json()["dataset_id"]
    assert biographic_client.post(action_url("biographic-dataset-process", dataset_id)).status_code == 200
    queued_tasks.reset_mock()

    response = biographic_client.post(action_url("biographic-dataset-approve", dataset_id))

    assert response.status_code == status.HTTP_409_CONFLICT
    dataset = BiographicSet.objects.get(pk=dataset_id)
    assert dataset.state == BiographicSet.State.PENDING
    assert dataset.group.processing_locked is True
    queued_tasks.assert_not_called()


def test_missing_token_is_401() -> None:
    response = APIClient().post(datasets_url(), {"records": [person()]}, format="json")
    assert response.status_code == status.HTTP_401_UNAUTHORIZED


def test_invalid_token_is_401() -> None:
    client = APIClient()
    client.credentials(HTTP_AUTHORIZATION="Token not-a-real-token")
    response = client.post(datasets_url(), {"records": [person()]}, format="json")
    assert response.status_code == status.HTTP_401_UNAUTHORIZED


def test_missing_biographic_grant_is_403() -> None:
    token = APITokenFactory(user=UserFactory(), grants=[Grant.API_DEDUP.value])
    client = create_api_client(token)
    response = client.post(datasets_url(), {"records": [person()]}, format="json")
    assert response.status_code == status.HTTP_403_FORBIDDEN


def test_group_lookup_recovers_from_a_create_race(biographic_client: APIClient, queued_tasks, mocker) -> None:
    group = BiographicGroupFactory(business_area="afghanistan", program_id="race")
    mocker.patch(
        "hope_dedup_engine.apps.biographic.services.BiographicGroup.objects.get_or_create",
        side_effect=IntegrityError,
    )

    response = biographic_client.post(
        datasets_url(program_id="race"),
        {"records": [person()]},
        format="json",
    )

    assert response.status_code == status.HTTP_201_CREATED
    assert BiographicSet.objects.get(pk=response.json()["dataset_id"]).group_id == group.pk


def _dataset_with_findings(state: str) -> BiographicSet:
    dataset = BiographicSetFactory(
        group=BiographicGroupFactory(business_area="afghanistan", program_id="prog-1"),
        state=state,
    )
    record = BiographicRecordFactory(dataset=dataset, reference_pk="cw-123")
    BiographicFindingFactory(
        record=record,
        matched_reference_pk="cw-456",
        score=8.2,
        proximity_to_score=2.2,
        scope=BiographicFinding.Scope.POPULATION,
        status_code=BiographicFinding.StatusCode.DUPLICATE,
        config={"duplicate_score": 6.0},
    )
    BiographicFindingFactory(
        record=record,
        matched_reference_pk="cw-789",
        score=8.0,
        proximity_to_score=2.0,
        scope=BiographicFinding.Scope.BATCH,
        status_code=BiographicFinding.StatusCode.DUPLICATE,
        config={"duplicate_score": 6.0},
    )
    return dataset


def _locked_dataset(state: str) -> BiographicSet:
    return BiographicSetFactory(
        group=BiographicGroupFactory(business_area="afghanistan", program_id="prog-1", processing_locked=True),
        state=state,
    )

import pytest
from rest_framework import status
from rest_framework.reverse import reverse
from rest_framework.test import APIClient

from api.api_const import DEDUPLICATION_SET_LIST_VIEW, JSON

from hope_dedup_engine.apps.api.models import DeduplicationSet
from hope_dedup_engine.apps.api.serializers import CreateDeduplicationSetSerializer


def test_can_create_deduplication_set(api_client: APIClient, deduplication_set_factory) -> None:
    previous_amount = DeduplicationSet.objects.count()
    data = CreateDeduplicationSetSerializer(deduplication_set_factory.build()).data

    response = api_client.post(reverse(DEDUPLICATION_SET_LIST_VIEW), data=data, format=JSON)

    assert response.status_code == status.HTTP_201_CREATED
    assert DeduplicationSet.objects.count() == previous_amount + 1
    data = response.json()
    assert data["state"] == DeduplicationSet.State.EMPTY.label


def test_missing_fields_handling(api_client: APIClient, deduplication_set_factory) -> None:
    data = CreateDeduplicationSetSerializer(deduplication_set_factory.build()).data
    del data["reference_pk"]

    response = api_client.post(reverse(DEDUPLICATION_SET_LIST_VIEW), data=data, format=JSON)

    assert response.status_code == status.HTTP_400_BAD_REQUEST
    errors = response.json()
    assert len(errors) == 1
    assert "reference_pk" in errors


@pytest.fixture
def active_ds_in_group(deduplication_set):
    deduplication_set.state = DeduplicationSet.State.READY
    deduplication_set.save(update_fields=["state"])
    return deduplication_set


def test_create_conflict_when_active_set_exists(api_client: APIClient, active_ds_in_group) -> None:
    data = {"reference_pk": active_ds_in_group.group.reference_pk}

    response = api_client.post(reverse(DEDUPLICATION_SET_LIST_VIEW), data=data, format=JSON)

    assert response.status_code == status.HTTP_409_CONFLICT


def test_create_in_a_group_without_active_sets_is_allowed(
    api_client: APIClient,
    deduplication_set_factory,
) -> None:
    """A group whose only set is rejected does not block the creation of a new one."""
    rejected = deduplication_set_factory(state=DeduplicationSet.State.REJECTED)

    response = api_client.post(
        reverse(DEDUPLICATION_SET_LIST_VIEW),
        data={"reference_pk": rejected.group.reference_pk},
        format=JSON,
    )

    assert response.status_code == status.HTTP_201_CREATED
    assert DeduplicationSet.objects.get(pk=response.json()["id"]).group == rejected.group


@pytest.mark.parametrize("field", ["reference_pk"])
def test_invalid_values_handling(field: str, api_client: APIClient, deduplication_set_factory) -> None:
    data = CreateDeduplicationSetSerializer(deduplication_set_factory.build()).data
    data[field] = None

    response = api_client.post(reverse(DEDUPLICATION_SET_LIST_VIEW), data=data, format=JSON)

    assert response.status_code == status.HTTP_400_BAD_REQUEST
    errors = response.json()
    assert len(errors) == 1
    assert field in errors


def test_create_with_duplicate_id_returns_400(api_client: APIClient, deduplication_set: DeduplicationSet) -> None:
    data = {"id": str(deduplication_set.pk), "reference_pk": "new-unique-ref"}

    response = api_client.post(reverse(DEDUPLICATION_SET_LIST_VIEW), data=data, format=JSON)

    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert "id" in response.json()


def test_create_uses_new_group_when_previous_group_deleted(
    api_client: APIClient,
    deduplication_set_group_factory,
) -> None:
    old_group = deduplication_set_group_factory(deleted=True)

    response = api_client.post(
        reverse(DEDUPLICATION_SET_LIST_VIEW),
        data={"reference_pk": old_group.reference_pk},
        format=JSON,
    )

    assert response.status_code == status.HTTP_201_CREATED

    deduplication_set = DeduplicationSet.objects.get(pk=response.json()["id"])
    assert deduplication_set.group_id != old_group.pk
    assert deduplication_set.group.reference_pk == old_group.reference_pk
    assert deduplication_set.group.deleted is False

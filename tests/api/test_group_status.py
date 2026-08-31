import pytest
from rest_framework import status
from rest_framework.reverse import reverse
from rest_framework.test import APIClient

from api.api_const import GROUP_STATUS_VIEW
from hope_dedup_engine.apps.api.models import DeduplicationSet


def status_url(reference_pk: str) -> str:
    return reverse(GROUP_STATUS_VIEW, kwargs={"reference_pk": reference_pk})


@pytest.mark.django_db
def test_can_create_when_no_sets_exist(api_client: APIClient) -> None:
    response = api_client.get(status_url("nonexistent-group"))
    assert response.status_code == status.HTTP_200_OK
    assert response.json()["can_create"] is True


@pytest.mark.django_db
@pytest.mark.parametrize(
    "deduplication_set__state",
    [
        DeduplicationSet.State.APPROVED,
        DeduplicationSet.State.REJECTED,
        DeduplicationSet.State.ENCODING_FAILED,
        DeduplicationSet.State.DEDUPLICATION_FAILED,
    ],
)
def test_can_create_when_all_sets_terminal(api_client: APIClient, deduplication_set: DeduplicationSet) -> None:
    response = api_client.get(status_url(deduplication_set.group.reference_pk))
    assert response.status_code == status.HTTP_200_OK
    assert response.json()["can_create"] is True


@pytest.mark.django_db
@pytest.mark.parametrize(
    "deduplication_set__state",
    [
        DeduplicationSet.State.EMPTY,
        DeduplicationSet.State.UPLOADING_IN_PROGRESS,
        DeduplicationSet.State.READY,
        DeduplicationSet.State.ENCODING_IN_PROGRESS,
        DeduplicationSet.State.ENCODED,
        DeduplicationSet.State.DEDUPLICATION_IN_PROGRESS,
        DeduplicationSet.State.DEDUPLICATED,
    ],
)
def test_cannot_create_when_active_set_exists(api_client: APIClient, deduplication_set: DeduplicationSet) -> None:
    response = api_client.get(status_url(deduplication_set.group.reference_pk))
    assert response.status_code == status.HTTP_200_OK
    assert response.json()["can_create"] is False

import pytest
from rest_framework import status
from rest_framework.reverse import reverse
from rest_framework.test import APIClient

from api.api_const import DEDUPLICATION_SET_READY_VIEW
from hope_dedup_engine.apps.api.models import DeduplicationSet


@pytest.fixture
def deduplication_set__state():
    return DeduplicationSet.State.UPLOADING_IN_PROGRESS


def test_ready_transitions_to_ready(api_client: APIClient, deduplication_set: DeduplicationSet) -> None:
    response = api_client.post(reverse(DEDUPLICATION_SET_READY_VIEW, (deduplication_set.pk,)))
    assert response.status_code == status.HTTP_200_OK
    deduplication_set.refresh_from_db()
    assert deduplication_set.state == DeduplicationSet.State.READY


@pytest.mark.parametrize(
    "state",
    [
        DeduplicationSet.State.EMPTY,
        DeduplicationSet.State.READY,
        DeduplicationSet.State.ENCODING_IN_PROGRESS,
        DeduplicationSet.State.ENCODED,
        DeduplicationSet.State.ENCODING_FAILED,
        DeduplicationSet.State.DEDUPLICATION_IN_PROGRESS,
        DeduplicationSet.State.DEDUPLICATED,
        DeduplicationSet.State.DEDUPLICATION_FAILED,
        DeduplicationSet.State.REJECTED,
    ],
)
def test_ready_rejects_disallowed_states(
    api_client: APIClient, deduplication_set: DeduplicationSet, state: int
) -> None:
    deduplication_set.state = state
    deduplication_set.save(update_fields=["state"])

    response = api_client.post(reverse(DEDUPLICATION_SET_READY_VIEW, (deduplication_set.pk,)))
    assert response.status_code == status.HTTP_409_CONFLICT
    deduplication_set.refresh_from_db()
    assert deduplication_set.state == state


@pytest.mark.parametrize(
    "deduplication_set__state",
    [DeduplicationSet.State.APPROVED],
)
def test_ready_not_found_for_excluded_states(api_client: APIClient, deduplication_set: DeduplicationSet) -> None:
    response = api_client.post(reverse(DEDUPLICATION_SET_READY_VIEW, (deduplication_set.pk,)))
    assert response.status_code == status.HTTP_404_NOT_FOUND

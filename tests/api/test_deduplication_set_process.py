from unittest.mock import MagicMock, patch

import pytest
from rest_framework import status
from rest_framework.reverse import reverse
from rest_framework.test import APIClient

from api.api_const import DEDUPLICATION_SET_PROCESS_VIEW
from hope_dedup_engine.apps.api.models import DeduplicationSet


@pytest.mark.parametrize(
    "deduplication_set__state",
    [
        DeduplicationSet.State.READY,
        DeduplicationSet.State.ENCODED,
        DeduplicationSet.State.ENCODING_FAILED,
        DeduplicationSet.State.DEDUPLICATION_FAILED,
    ],
)
@patch("hope_dedup_engine.apps.api.views.MainJob.queue")
def test_can_trigger_deduplication_set_processing(
    mock_dedup_job_queue: MagicMock,
    api_client: APIClient,
    deduplication_set: DeduplicationSet,
) -> None:
    response = api_client.post(reverse(DEDUPLICATION_SET_PROCESS_VIEW, (deduplication_set.pk,)))
    assert response.status_code == status.HTTP_200_OK
    mock_dedup_job_queue.assert_called_once()


@pytest.mark.parametrize(
    "deduplication_set__state",
    [
        DeduplicationSet.State.EMPTY,
        DeduplicationSet.State.UPLOADING_IN_PROGRESS,
        DeduplicationSet.State.ENCODING_IN_PROGRESS,
        DeduplicationSet.State.DEDUPLICATION_IN_PROGRESS,
        DeduplicationSet.State.DEDUPLICATED,
        DeduplicationSet.State.REJECTED,
    ],
)
def test_cannot_trigger_processing_in_non_processable_state(
    api_client: APIClient,
    deduplication_set: DeduplicationSet,
) -> None:
    response = api_client.post(reverse(DEDUPLICATION_SET_PROCESS_VIEW, (deduplication_set.pk,)))
    assert response.status_code == status.HTTP_409_CONFLICT


@pytest.mark.parametrize(
    "deduplication_set__state",
    [
        DeduplicationSet.State.APPROVED,
    ],
)
def test_cannot_trigger_processing_for_excluded_states(
    api_client: APIClient,
    deduplication_set: DeduplicationSet,
) -> None:
    response = api_client.post(reverse(DEDUPLICATION_SET_PROCESS_VIEW, (deduplication_set.pk,)))
    assert response.status_code == status.HTTP_404_NOT_FOUND


@patch("hope_dedup_engine.apps.api.views.MainJob.queue")
def test_cannot_process_when_group_locked(
    mock_dedup_job_queue: MagicMock,
    api_client: APIClient,
    deduplication_set: DeduplicationSet,
) -> None:
    deduplication_set.group.processing_locked = True
    deduplication_set.group.save(update_fields=["processing_locked"])

    response = api_client.post(reverse(DEDUPLICATION_SET_PROCESS_VIEW, (deduplication_set.pk,)))
    assert response.status_code == status.HTTP_409_CONFLICT
    mock_dedup_job_queue.assert_not_called()

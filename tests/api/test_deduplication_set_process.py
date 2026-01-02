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
        DeduplicationSet.State.MODIFIED,
        DeduplicationSet.State.FAILED,
    ],
)
@patch("hope_dedup_engine.apps.api.views.MainJob.queue")
def test_can_trigger_deduplication_set_processing(
    mock_dedup_job_queue: MagicMock,
    api_client: APIClient,
    deduplication_set: DeduplicationSet,
) -> None:
    response = api_client.post(reverse(DEDUPLICATION_SET_PROCESS_VIEW, (deduplication_set.group.reference_pk,)))
    assert response.status_code == status.HTTP_200_OK
    mock_dedup_job_queue.assert_called_once()  # queue()

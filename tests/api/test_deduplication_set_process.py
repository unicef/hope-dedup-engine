from unittest.mock import MagicMock

from api_const import DEDUPLICATION_SET_PROCESS_VIEW
from pytest import mark
from rest_framework import status
from rest_framework.reverse import reverse
from rest_framework.test import APIClient

from hope_dedup_engine.apps.api.models import DeduplicationSet
from hope_dedup_engine.apps.api.utils import AlreadyProcessingError


@mark.parametrize(
    "deduplication_set__state",
    (
        DeduplicationSet.State.CLEAN,
        DeduplicationSet.State.DIRTY,
        DeduplicationSet.State.PROCESSING,
        DeduplicationSet.State.ERROR,
    ),
)
def test_can_trigger_deduplication_set_processing_in_any_state(
    api_client: APIClient,
    start_processing: MagicMock,
    deduplication_set: DeduplicationSet,
    requests_get_mock: MagicMock,
) -> None:
    response = api_client.post(
        reverse(DEDUPLICATION_SET_PROCESS_VIEW, (deduplication_set.pk,))
    )
    assert response.status_code == status.HTTP_200_OK
    start_processing.assert_called_once_with(deduplication_set)


def test_cannot_trigger_deduplication_set_processing_when_already_processing(
    api_client: APIClient,
    start_processing: MagicMock,
    deduplication_set: DeduplicationSet,
) -> None:
    start_processing.side_effect = AlreadyProcessingError
    response = api_client.post(
        reverse(DEDUPLICATION_SET_PROCESS_VIEW, (deduplication_set.pk,))
    )
    assert response.status_code == status.HTTP_409_CONFLICT

from unittest.mock import MagicMock

from api_const import (
    DEDUPLICATION_SET_DETAIL_VIEW,
    DEDUPLICATION_SET_LIST_VIEW,
    DEDUPLICATION_SET_PROCESS_VIEW,
    IMAGE_LIST_VIEW,
    JSON,
)
from pytest import mark
from rest_framework import status
from rest_framework.reverse import reverse
from rest_framework.test import APIClient
from testutils.factories.api import DeduplicationSetFactory, ImageFactory

from hope_dedup_engine.apps.public_api.models import DeduplicationSet
from hope_dedup_engine.apps.public_api.serializers import DeduplicationSetSerializer, ImageSerializer


def test_new_deduplication_set_status_is_clean(api_client: APIClient) -> None:
    data = DeduplicationSetSerializer(DeduplicationSetFactory.build()).data

    response = api_client.post(reverse(DEDUPLICATION_SET_LIST_VIEW), data=data, format=JSON)
    assert response.status_code == status.HTTP_201_CREATED
    deduplication_set = response.json()
    assert deduplication_set["state"] == DeduplicationSet.State.CLEAN.label


@mark.parametrize(
    "deduplication_set__state",
    (DeduplicationSet.State.CLEAN, DeduplicationSet.State.DIRTY, DeduplicationSet.State.ERROR),
)
def test_deduplication_set_processing_trigger(
    api_client: APIClient, start_processing: MagicMock, deduplication_set: DeduplicationSet
) -> None:
    response = api_client.post(reverse(DEDUPLICATION_SET_PROCESS_VIEW, (deduplication_set.pk,)))
    assert response.status_code == status.HTTP_200_OK
    start_processing.delay.assert_called_once_with(deduplication_set.pk)


def test_new_image_makes_deduplication_set_state_dirty(
    api_client: APIClient, deduplication_set: DeduplicationSet
) -> None:
    assert deduplication_set.state == DeduplicationSet.State.CLEAN
    response = api_client.post(
        reverse(IMAGE_LIST_VIEW, (deduplication_set.pk,)), data=ImageSerializer(ImageFactory.build()).data, format=JSON
    )
    assert response.status_code == status.HTTP_201_CREATED
    deduplication_set.refresh_from_db()
    assert deduplication_set.state == DeduplicationSet.State.DIRTY


def test_can_deletion_triggers_model_data_deletion(
    api_client: APIClient, deduplication_set: DeduplicationSet, delete_model_data: MagicMock
) -> None:
    response = api_client.delete(reverse(DEDUPLICATION_SET_DETAIL_VIEW, (deduplication_set.pk,)))
    assert response.status_code == status.HTTP_204_NO_CONTENT
    delete_model_data.assert_called_once_with(deduplication_set)


def test_unauthorized_deletion_does_not_trigger_model_data_deletion(
    another_system_api_client: APIClient, deduplication_set: DeduplicationSet, delete_model_data: MagicMock
) -> None:
    response = another_system_api_client.delete(reverse(DEDUPLICATION_SET_DETAIL_VIEW, (deduplication_set.pk,)))
    assert response.status_code == status.HTTP_403_FORBIDDEN
    delete_model_data.assert_not_called()

from unittest.mock import MagicMock

from const import DEDUPLICATION_SET_DETAIL_VIEW
from rest_framework import status
from rest_framework.reverse import reverse
from rest_framework.test import APIClient

from hope_dedup_engine.apps.public_api.models import DeduplicationSet
from hope_dedup_engine.apps.security.models import User


def test_can_delete_deduplication_set(
    api_client: APIClient, user: User, deduplication_set: DeduplicationSet, delete_model_data: MagicMock
) -> None:
    assert not deduplication_set.deleted
    assert deduplication_set.updated_by is None
    previous_amount = DeduplicationSet.objects.count()

    response = api_client.delete(reverse(DEDUPLICATION_SET_DETAIL_VIEW, (deduplication_set.pk,)))
    assert response.status_code == status.HTTP_204_NO_CONTENT

    # object is only marked as deleted
    assert DeduplicationSet.objects.count() == previous_amount
    deduplication_set.refresh_from_db()
    assert deduplication_set.deleted
    assert deduplication_set.updated_by == user
    delete_model_data.assert_called_once_with(deduplication_set)


def test_cannot_delete_deduplication_set_between_systems(
    another_system_api_client: APIClient, deduplication_set: DeduplicationSet, delete_model_data: MagicMock
) -> None:
    response = another_system_api_client.delete(reverse(DEDUPLICATION_SET_DETAIL_VIEW, (deduplication_set.pk,)))
    assert response.status_code == status.HTTP_403_FORBIDDEN
    delete_model_data.assert_not_called()

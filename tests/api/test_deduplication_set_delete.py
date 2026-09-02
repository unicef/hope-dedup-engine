from unittest.mock import MagicMock

from rest_framework import status
from rest_framework.reverse import reverse
from rest_framework.test import APIClient

from api.api_const import DEDUPLICATION_SET_DETAIL_VIEW
from hope_dedup_engine.apps.api.models import DeduplicationSet
from hope_dedup_engine.apps.security.models import User


def test_can_delete_deduplication_set(
    api_client: APIClient,
    user: User,
    deduplication_set: DeduplicationSet,
    delete_model_data: MagicMock,
) -> None:
    assert deduplication_set.updated_by is None

    response = api_client.delete(reverse(DEDUPLICATION_SET_DETAIL_VIEW, (deduplication_set.pk,)))
    assert response.status_code == status.HTTP_204_NO_CONTENT

    deduplication_set.refresh_from_db()
    assert deduplication_set.updated_by == user
    delete_model_data.assert_called_once_with(deduplication_set)

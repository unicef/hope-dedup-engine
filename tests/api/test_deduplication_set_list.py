from rest_framework import status
from rest_framework.reverse import reverse
from rest_framework.test import APIClient

from api.api_const import DEDUPLICATION_SET_LIST_VIEW
from hope_dedup_engine.apps.api.models import DeduplicationSet


def test_can_list_deduplication_sets(api_client: APIClient, deduplication_set: DeduplicationSet) -> None:
    response = api_client.get(reverse(DEDUPLICATION_SET_LIST_VIEW))
    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert len(data) == 1

from const import DEDUPLICATION_SET_LIST_VIEW
from rest_framework import status
from rest_framework.reverse import reverse
from rest_framework.test import APIClient

from hope_dedup_engine.apps.public_api.models import DeduplicationSet


def test_can_list_deduplication_sets(api_client: APIClient, deduplication_set: DeduplicationSet) -> None:
    response = api_client.get(reverse(DEDUPLICATION_SET_LIST_VIEW))
    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert len(data) == 1


def test_cannot_list_deduplication_sets_between_systems(
    another_system_api_client: APIClient, deduplication_set: DeduplicationSet
) -> None:
    assert DeduplicationSet.objects.count()
    response = another_system_api_client.get(reverse(DEDUPLICATION_SET_LIST_VIEW))
    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert len(data) == 0

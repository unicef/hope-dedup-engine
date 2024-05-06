from const import DEDUPLICATION_SET_LIST
from conftest import create_api_client
from rest_framework import status
from rest_framework.reverse import reverse
from rest_framework.test import APIClient

from hope_dedup_engine.apps.public_api.models import DeduplicationSet
from testutils.factories import UserFactory


def test_can_list_deduplication_sets(authenticated_api_client: APIClient, deduplication_set: DeduplicationSet) -> None:
    response = authenticated_api_client.get(reverse(DEDUPLICATION_SET_LIST))
    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert len(data) == 1


def test_cannot_list_another_system_deduplication_sets(deduplication_set: DeduplicationSet) -> None:
    user = UserFactory()
    client = create_api_client(user)
    assert user.external_system != deduplication_set.external_system

    response = client.get(reverse(DEDUPLICATION_SET_LIST))
    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert len(data) == 0

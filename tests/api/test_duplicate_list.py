from api_const import DUPLICATE_LIST_VIEW
from rest_framework import status
from rest_framework.reverse import reverse
from rest_framework.test import APIClient

from hope_dedup_engine.apps.api.models import DeduplicationSet
from hope_dedup_engine.apps.api.models.deduplication import Duplicate


def test_can_list_duplicates(
    api_client: APIClient, deduplication_set: DeduplicationSet, duplicate: Duplicate
) -> None:
    response = api_client.get(reverse(DUPLICATE_LIST_VIEW, (deduplication_set.pk,)))
    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert len(data) == 1


def test_cannot_list_duplicates_between_systems(
    another_system_api_client: APIClient,
    deduplication_set: DeduplicationSet,
    duplicate: Duplicate,
) -> None:
    assert DeduplicationSet.objects.count()
    response = another_system_api_client.get(
        reverse(DUPLICATE_LIST_VIEW, (deduplication_set.pk,))
    )
    assert response.status_code == status.HTTP_403_FORBIDDEN

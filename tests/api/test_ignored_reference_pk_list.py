from api_const import IGNORED_REFERENCE_PK_LIST_VIEW
from rest_framework import status
from rest_framework.reverse import reverse
from rest_framework.test import APIClient

from hope_dedup_engine.apps.api.models import DeduplicationSet
from hope_dedup_engine.apps.api.models.deduplication import IgnoredReferencePkPair


def test_can_list_ignored_reference_pk_pairs(
    api_client: APIClient,
    deduplication_set: DeduplicationSet,
    ignored_reference_pk_pair: IgnoredReferencePkPair,
) -> None:
    response = api_client.get(
        reverse(IGNORED_REFERENCE_PK_LIST_VIEW, (deduplication_set.pk,))
    )
    assert response.status_code == status.HTTP_200_OK
    ignored_reference_pk_pairs = response.json()
    assert len(ignored_reference_pk_pairs)
    assert (
        len(ignored_reference_pk_pairs)
        == IgnoredReferencePkPair.objects.filter(
            deduplication_set=deduplication_set
        ).count()
    )


def test_cannot_list_ignored_reference_pk_pairs_between_systems(
    another_system_api_client: APIClient, deduplication_set: DeduplicationSet
) -> None:
    response = another_system_api_client.get(
        reverse(IGNORED_REFERENCE_PK_LIST_VIEW, (deduplication_set.pk,))
    )
    assert response.status_code == status.HTTP_403_FORBIDDEN

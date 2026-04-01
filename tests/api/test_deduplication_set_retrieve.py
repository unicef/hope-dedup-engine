import typing

from rest_framework import status
from rest_framework.reverse import reverse
from rest_framework.test import APIClient

from api.api_const import DEDUPLICATION_SET_DETAIL_VIEW
from hope_dedup_engine.apps.api.models import DeduplicationSet
from hope_dedup_engine.apps.api.serializers import DeduplicationSetSerializer


if typing.TYPE_CHECKING:
    from hope_dedup_engine.apps.api.models.deduplication import Finding


def test_can_retrieve_deduplication_set(api_client: APIClient, deduplication_set: DeduplicationSet) -> None:
    response = api_client.get(reverse(DEDUPLICATION_SET_DETAIL_VIEW, (deduplication_set.pk,)))
    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert data["id"] == str(deduplication_set.pk)


def test_serializer_computes_findings_count_without_annotation(
    deduplication_set: DeduplicationSet, finding: "Finding"
) -> None:
    data = DeduplicationSetSerializer(deduplication_set).data
    assert data["findings_count"] == 1

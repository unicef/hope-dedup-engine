from api_const import DEDUPLICATION_SET_LIST_VIEW, JSON
from rest_framework import status
from rest_framework.reverse import reverse
from rest_framework.test import APIClient
from testutils.factories.api import DeduplicationSetFactory

from hope_dedup_engine.apps.api.models import DeduplicationSet
from hope_dedup_engine.apps.api.serializers import DeduplicationSetSerializer


def test_can_create_deduplication_set(api_client: APIClient) -> None:
    previous_amount = DeduplicationSet.objects.count()
    data = DeduplicationSetSerializer(DeduplicationSetFactory.build()).data

    response = api_client.post(
        reverse(DEDUPLICATION_SET_LIST_VIEW), data=data, format=JSON
    )
    assert response.status_code == status.HTTP_201_CREATED
    assert DeduplicationSet.objects.count() == previous_amount + 1
    data = response.json()
    assert data["state"] == DeduplicationSet.State.CLEAN.label


def test_missing_fields_handling(api_client: APIClient) -> None:
    data = DeduplicationSetSerializer(DeduplicationSetFactory.build()).data
    del data["reference_pk"]

    response = api_client.post(
        reverse(DEDUPLICATION_SET_LIST_VIEW), data=data, format=JSON
    )
    assert response.status_code == status.HTTP_400_BAD_REQUEST
    errors = response.json()
    assert len(errors) == 1
    assert "reference_pk" in errors


def test_invalid_values_handling(api_client: APIClient) -> None:
    data = DeduplicationSetSerializer(DeduplicationSetFactory.build()).data
    data["reference_pk"] = None
    response = api_client.post(
        reverse(DEDUPLICATION_SET_LIST_VIEW), data=data, format=JSON
    )
    assert response.status_code == status.HTTP_400_BAD_REQUEST
    errors = response.json()
    assert len(errors) == 1
    assert "reference_pk" in errors

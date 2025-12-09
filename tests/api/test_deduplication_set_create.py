import pytest
from rest_framework import status
from rest_framework.reverse import reverse
from rest_framework.test import APIClient

from api.api_const import DEDUPLICATION_SET_LIST_VIEW, JSON
from testutils.factories.api import DeduplicationSetFactory

from hope_dedup_engine.apps.api.models import DeduplicationSet
from hope_dedup_engine.apps.api.serializers import CreateDeduplicationSetSerializer


def test_can_create_deduplication_set(api_client: APIClient) -> None:
    previous_amount = DeduplicationSet.objects.count()
    data = CreateDeduplicationSetSerializer(DeduplicationSetFactory.build()).data

    response = api_client.post(reverse(DEDUPLICATION_SET_LIST_VIEW), data=data, format=JSON)

    assert response.status_code == status.HTTP_201_CREATED
    assert DeduplicationSet.objects.count() == previous_amount + 1
    data = response.json()
    assert data["state"] == DeduplicationSet.State.READY.label


def test_missing_fields_handling(api_client: APIClient) -> None:
    data = CreateDeduplicationSetSerializer(DeduplicationSetFactory.build()).data
    del data["reference_pk"]

    response = api_client.post(reverse(DEDUPLICATION_SET_LIST_VIEW), data=data, format=JSON)

    assert response.status_code == status.HTTP_400_BAD_REQUEST
    errors = response.json()
    assert len(errors) == 1
    assert "reference_pk" in errors


@pytest.mark.parametrize("field", ["reference_pk", "settings"])
def test_invalid_values_handling(field: str, api_client: APIClient) -> None:
    data = CreateDeduplicationSetSerializer(DeduplicationSetFactory.build()).data
    data[field] = None

    response = api_client.post(reverse(DEDUPLICATION_SET_LIST_VIEW), data=data, format=JSON)

    assert response.status_code == status.HTTP_400_BAD_REQUEST
    errors = response.json()
    assert len(errors) == 1
    assert field in errors

from typing import Any

from pytest import mark
from rest_framework import status
from rest_framework.reverse import reverse
from rest_framework.test import APIClient

from hope_dedup_engine.apps.public_api.models import DeduplicationSet
from hope_dedup_engine.apps.public_api.serializers import DeduplicationSetSerializer
from hope_dedup_engine.apps.public_api.urls import DEDUPLICATION_SET
from testutils.factories.api import DeduplicationSetFactory

DEDUPLICATION_SET_LIST = f"{DEDUPLICATION_SET}-list"
URL = reverse("deduplication_set-list")


def test_can_create_deduplication_set(authenticated_api_client: APIClient) -> None:
    previous_amount = DeduplicationSet.objects.count()
    data = DeduplicationSetSerializer(DeduplicationSetFactory.build()).data
    response = authenticated_api_client.post(URL, data=data, format="json")
    assert response.status_code == status.HTTP_201_CREATED
    assert DeduplicationSet.objects.count() == previous_amount + 1


@mark.parametrize(
    "omit",
    (
        "name",
        "reference_pk",
        ("name", "reference_pk"),
    ),
)
def test_missing_fields_handling(authenticated_api_client: APIClient, omit: str | tuple[str, ...]) -> None:
    data = DeduplicationSetSerializer(DeduplicationSetFactory.build()).data
    missing_fields = (omit,) if isinstance(omit, str) else omit
    for field in missing_fields:
        del data[field]

    response = authenticated_api_client.post(URL, data=data, format="json")
    assert response.status_code == status.HTTP_400_BAD_REQUEST
    errors = response.json()
    assert len(errors) == len(missing_fields)
    for field in missing_fields:
        assert field in errors


@mark.parametrize(
    ("field", "value"),
    (
        ("name", ""),
        ("name", None),
        ("reference_pk", "foo"),
        ("reference_pk", None),
        ("reference_pk", 3.14),
    ),
)
def test_invalid_values_handling(authenticated_api_client: APIClient, field: str, value: Any) -> None:
    data = DeduplicationSetSerializer(DeduplicationSetFactory.build()).data
    data[field] = value
    response = authenticated_api_client.post(URL, data=data, format="json")
    assert response.status_code == status.HTTP_400_BAD_REQUEST
    errors = response.json()
    assert len(errors) == 1
    assert field in errors

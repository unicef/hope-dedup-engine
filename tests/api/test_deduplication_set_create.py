from typing import Any

from const import DEDUPLICATION_SET_LIST_VIEW
from pytest import mark
from rest_framework import status
from rest_framework.reverse import reverse
from rest_framework.test import APIClient

from hope_dedup_engine.apps.public_api.models import DeduplicationSet
from hope_dedup_engine.apps.public_api.serializers import DeduplicationSetSerializer
from testutils.factories.api import DeduplicationSetFactory


def test_can_create_deduplication_set(api_client: APIClient) -> None:
    previous_amount = DeduplicationSet.objects.count()
    data = DeduplicationSetSerializer(DeduplicationSetFactory.build()).data

    response = api_client.post(reverse(DEDUPLICATION_SET_LIST_VIEW), data=data, format="json")
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
def test_missing_fields_handling(api_client: APIClient, omit: str | tuple[str, ...]) -> None:
    data = DeduplicationSetSerializer(DeduplicationSetFactory.build()).data
    missing_fields = (omit,) if isinstance(omit, str) else omit
    for field in missing_fields:
        del data[field]

    response = api_client.post(reverse(DEDUPLICATION_SET_LIST_VIEW), data=data, format="json")
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
def test_invalid_values_handling(api_client: APIClient, field: str, value: Any) -> None:
    data = DeduplicationSetSerializer(DeduplicationSetFactory.build()).data
    data[field] = value
    response = api_client.post(reverse(DEDUPLICATION_SET_LIST_VIEW), data=data, format="json")
    assert response.status_code == status.HTTP_400_BAD_REQUEST
    errors = response.json()
    assert len(errors) == 1
    assert field in errors

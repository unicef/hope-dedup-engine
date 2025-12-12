import pytest
from rest_framework import status
from rest_framework.reverse import reverse
from rest_framework.test import APIClient

from api.api_const import ENCODING_LIST_VIEW, JSON
from testutils.factories.api import EncodingFactory

from hope_dedup_engine.apps.api.models import DeduplicationSet
from hope_dedup_engine.apps.api.models.deduplication import Encoding
from hope_dedup_engine.apps.api.serializers import EncodingSerializer
from hope_dedup_engine.apps.security.models import User


def test_can_create_image(
    api_client: APIClient,
    deduplication_set: DeduplicationSet,
) -> None:
    previous_amount = Encoding.objects.filter(deduplication_set=deduplication_set).count()
    data = EncodingSerializer(EncodingFactory.build()).data
    assert deduplication_set.state == DeduplicationSet.State.READY

    response = api_client.post(
        reverse(ENCODING_LIST_VIEW, (deduplication_set.group.reference_pk,)), data=data, format=JSON
    )
    assert response.status_code == status.HTTP_201_CREATED
    assert Encoding.objects.filter(deduplication_set=deduplication_set).count() == previous_amount + 1

    deduplication_set.refresh_from_db()
    assert deduplication_set.state == DeduplicationSet.State.MODIFIED


def test_cannot_create_image_between_systems(
    another_system_api_client: APIClient, deduplication_set: DeduplicationSet
) -> None:
    previous_amount = Encoding.objects.filter(deduplication_set=deduplication_set).count()
    data = EncodingSerializer(EncodingFactory.build()).data

    response = another_system_api_client.post(
        reverse(ENCODING_LIST_VIEW, (deduplication_set.group.reference_pk,)), data=data, format=JSON
    )
    assert response.status_code == status.HTTP_403_FORBIDDEN
    assert Encoding.objects.filter(deduplication_set=deduplication_set).count() == previous_amount


@pytest.mark.parametrize(
    "filename",
    [
        "",
        None,
    ],
)
def test_invalid_values_handling(
    api_client: APIClient, deduplication_set: DeduplicationSet, filename: str | None
) -> None:
    data = EncodingSerializer(EncodingFactory.build()).data
    data["filename"] = filename
    response = api_client.post(
        reverse(ENCODING_LIST_VIEW, (deduplication_set.group.reference_pk,)), data=data, format=JSON
    )
    assert response.status_code == status.HTTP_400_BAD_REQUEST
    errors = response.json()
    assert len(errors) == 1
    assert "filename" in errors


def test_missing_filename_handling(api_client: APIClient, deduplication_set: DeduplicationSet) -> None:
    data = EncodingSerializer(EncodingFactory.build()).data
    del data["filename"]

    response = api_client.post(
        reverse(ENCODING_LIST_VIEW, (deduplication_set.group.reference_pk,)), data=data, format=JSON
    )
    assert response.status_code == status.HTTP_400_BAD_REQUEST
    errors = response.json()
    assert "filename" in errors


def test_deduplication_set_is_updated(
    api_client: APIClient,
    user: User,
    deduplication_set: DeduplicationSet,
) -> None:
    assert deduplication_set.updated_by is None

    data = EncodingSerializer(EncodingFactory.build()).data
    response = api_client.post(
        reverse(ENCODING_LIST_VIEW, (deduplication_set.group.reference_pk,)), data=data, format=JSON
    )

    assert response.status_code == status.HTTP_201_CREATED
    deduplication_set.refresh_from_db()
    assert deduplication_set.updated_by == user


def test_image_with_same_reference_pk_is_updated(
    api_client: APIClient,
    deduplication_set: DeduplicationSet,
) -> None:
    image = EncodingFactory.create(deduplication_set=deduplication_set)

    data = EncodingSerializer(image).data
    new_filename = "new_filename.jpg"
    data["filename"] = new_filename
    response = api_client.post(
        reverse(ENCODING_LIST_VIEW, (deduplication_set.group.reference_pk,)), data=data, format=JSON
    )

    assert response.status_code == status.HTTP_201_CREATED
    image.refresh_from_db()
    assert image.filename == new_filename
    assert Encoding.objects.count() == 1

from api_const import IMAGE_LIST_VIEW, JSON
from pytest import mark
from rest_framework import status
from rest_framework.reverse import reverse
from rest_framework.test import APIClient
from testutils.factories.api import ImageFactory

from hope_dedup_engine.apps.api.models import DeduplicationSet
from hope_dedup_engine.apps.api.models.deduplication import Image
from hope_dedup_engine.apps.api.serializers import ImageSerializer
from hope_dedup_engine.apps.security.models import User


def test_can_create_image(api_client: APIClient, deduplication_set: DeduplicationSet) -> None:
    previous_amount = Image.objects.filter(deduplication_set=deduplication_set).count()
    data = ImageSerializer(ImageFactory.build()).data

    response = api_client.post(reverse(IMAGE_LIST_VIEW, (deduplication_set.pk,)), data=data, format=JSON)
    assert response.status_code == status.HTTP_201_CREATED
    assert Image.objects.filter(deduplication_set=deduplication_set).count() == previous_amount + 1


def test_cannot_create_image_between_systems(
    another_system_api_client: APIClient, deduplication_set: DeduplicationSet
) -> None:
    previous_amount = Image.objects.filter(deduplication_set=deduplication_set).count()
    data = ImageSerializer(ImageFactory.build()).data

    response = another_system_api_client.post(reverse(IMAGE_LIST_VIEW, (deduplication_set.pk,)), data=data, format=JSON)
    assert response.status_code == status.HTTP_403_FORBIDDEN
    assert Image.objects.filter(deduplication_set=deduplication_set).count() == previous_amount


@mark.parametrize(
    "filename",
    (
        "",
        None,
    ),
)
def test_invalid_values_handling(
    api_client: APIClient, deduplication_set: DeduplicationSet, filename: str | None
) -> None:
    data = ImageSerializer(ImageFactory.build()).data
    data["filename"] = filename
    response = api_client.post(reverse(IMAGE_LIST_VIEW, (deduplication_set.pk,)), data=data, format=JSON)
    assert response.status_code == status.HTTP_400_BAD_REQUEST
    errors = response.json()
    assert len(errors) == 1
    assert "filename" in errors


def test_missing_filename_handling(api_client: APIClient, deduplication_set: DeduplicationSet) -> None:
    data = ImageSerializer(ImageFactory.build()).data
    del data["filename"]

    response = api_client.post(reverse(IMAGE_LIST_VIEW, (deduplication_set.pk,)), data=data, format=JSON)
    assert response.status_code == status.HTTP_400_BAD_REQUEST
    errors = response.json()
    assert "filename" in errors


def test_deduplication_set_is_updated(api_client: APIClient, user: User, deduplication_set: DeduplicationSet) -> None:
    assert deduplication_set.updated_by is None

    data = ImageSerializer(ImageFactory.build()).data
    response = api_client.post(reverse(IMAGE_LIST_VIEW, (deduplication_set.pk,)), data=data, format=JSON)

    assert response.status_code == status.HTTP_201_CREATED
    deduplication_set.refresh_from_db()
    assert deduplication_set.updated_by == user

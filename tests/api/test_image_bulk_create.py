from rest_framework import status
from rest_framework.reverse import reverse
from rest_framework.test import APIClient

from api.api_const import BULK_IMAGE_LIST_VIEW, JSON
from testutils.factories.api import EncodingFactory

from hope_dedup_engine.apps.api.models import DeduplicationSet, Encoding
from hope_dedup_engine.apps.api.serializers import EncodingSerializer
from hope_dedup_engine.apps.security.models import User


def test_can_bulk_create_images(api_client: APIClient, deduplication_set: DeduplicationSet) -> None:
    data = EncodingSerializer(EncodingFactory.build_batch(10), many=True).data
    response = api_client.post(reverse(BULK_IMAGE_LIST_VIEW, (deduplication_set.pk,)), data=data, format=JSON)
    assert response.status_code == status.HTTP_201_CREATED


def test_cannot_bulk_create_images_between_systems(
    another_system_api_client: APIClient, deduplication_set: DeduplicationSet
) -> None:
    data = EncodingSerializer(EncodingFactory.build_batch(10), many=True).data
    response = another_system_api_client.post(
        reverse(BULK_IMAGE_LIST_VIEW, (deduplication_set.pk,)), data=data, format=JSON
    )
    assert response.status_code == status.HTTP_403_FORBIDDEN


def test_deduplication_set_is_updated(api_client: APIClient, user: User, deduplication_set: DeduplicationSet) -> None:
    assert deduplication_set.updated_by is None

    data = EncodingSerializer(EncodingFactory.build_batch(10), many=True).data
    response = api_client.post(reverse(BULK_IMAGE_LIST_VIEW, (deduplication_set.pk,)), data=data, format=JSON)

    assert response.status_code == status.HTTP_201_CREATED
    deduplication_set.refresh_from_db()
    assert deduplication_set.updated_by == user


def test_images_with_same_reference_pk_is_updated(api_client: APIClient, deduplication_set: DeduplicationSet) -> None:
    number_of_images = 10
    images = EncodingFactory.create_batch(number_of_images, deduplication_set=deduplication_set)

    data = EncodingSerializer(images, many=True).data
    new_filenames = {f"new_filename_{i}.jpg" for i in range(number_of_images)}
    for image_data, new_filename in zip(data, new_filenames, strict=False):
        image_data["filename"] = new_filename
    response = api_client.post(reverse(BULK_IMAGE_LIST_VIEW, (deduplication_set.pk,)), data=data, format=JSON)

    assert response.status_code == status.HTTP_201_CREATED
    assert Encoding.objects.count() == number_of_images
    for image in images:
        image.refresh_from_db()
    filenames = {image.filename for image in images}
    assert filenames == new_filenames

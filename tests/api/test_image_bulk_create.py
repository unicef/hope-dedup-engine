from api_const import BULK_IMAGE_LIST_VIEW, JSON
from rest_framework import status
from rest_framework.reverse import reverse
from rest_framework.test import APIClient
from testutils.factories.api import ImageFactory

from hope_dedup_engine.apps.public_api.models import DeduplicationSet
from hope_dedup_engine.apps.public_api.serializers import ImageSerializer
from hope_dedup_engine.apps.security.models import User


def test_can_bulk_create_images(api_client: APIClient, deduplication_set: DeduplicationSet) -> None:
    data = ImageSerializer(ImageFactory.build_batch(10), many=True).data
    response = api_client.post(reverse(BULK_IMAGE_LIST_VIEW, (deduplication_set.pk,)), data=data, format=JSON)
    assert response.status_code == status.HTTP_201_CREATED


def test_cannot_bulk_create_images_between_systems(
    another_system_api_client: APIClient, deduplication_set: DeduplicationSet
) -> None:
    data = ImageSerializer(ImageFactory.build_batch(10), many=True).data
    response = another_system_api_client.post(
        reverse(BULK_IMAGE_LIST_VIEW, (deduplication_set.pk,)), data=data, format=JSON
    )
    assert response.status_code == status.HTTP_403_FORBIDDEN


def test_deduplication_set_is_updated(api_client: APIClient, user: User, deduplication_set: DeduplicationSet) -> None:
    assert deduplication_set.updated_by is None

    data = ImageSerializer(ImageFactory.build_batch(10), many=True).data
    response = api_client.post(reverse(BULK_IMAGE_LIST_VIEW, (deduplication_set.pk,)), data=data, format=JSON)

    assert response.status_code == status.HTTP_201_CREATED
    deduplication_set.refresh_from_db()
    assert deduplication_set.updated_by == user

from api_const import IMAGE_LIST_VIEW
from rest_framework import status
from rest_framework.reverse import reverse
from rest_framework.test import APIClient

from hope_dedup_engine.apps.api.models import DeduplicationSet
from hope_dedup_engine.apps.api.models.deduplication import Image


def test_can_list_images(
    api_client: APIClient, deduplication_set: DeduplicationSet, image: Image
) -> None:
    response = api_client.get(reverse(IMAGE_LIST_VIEW, (deduplication_set.pk,)))
    assert response.status_code == status.HTTP_200_OK
    images = response.json()
    assert len(images)
    assert (
        len(images) == Image.objects.filter(deduplication_set=deduplication_set).count()
    )


def test_cannot_list_images_between_systems(
    another_system_api_client: APIClient, deduplication_set: DeduplicationSet
) -> None:
    response = another_system_api_client.get(
        reverse(IMAGE_LIST_VIEW, (deduplication_set.pk,))
    )
    assert response.status_code == status.HTTP_403_FORBIDDEN

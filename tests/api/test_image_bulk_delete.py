from const import BULK_IMAGE_CLEAR_VIEW
from rest_framework import status
from rest_framework.reverse import reverse
from rest_framework.test import APIClient

from hope_dedup_engine.apps.public_api.models import DeduplicationSet
from hope_dedup_engine.apps.public_api.models.deduplication import Image
from hope_dedup_engine.apps.security.models import User


def test_can_delete_all_images(api_client: APIClient, deduplication_set: DeduplicationSet, image: Image) -> None:
    image_count = Image.objects.filter(deduplication_set=deduplication_set).count()
    response = api_client.delete(reverse(BULK_IMAGE_CLEAR_VIEW, (deduplication_set.pk,)))
    assert response.status_code == status.HTTP_204_NO_CONTENT
    assert Image.objects.filter(deduplication_set=deduplication_set).count() == image_count - 1


def test_cannot_delete_images_between_systems(
    another_system_api_client: APIClient, deduplication_set: DeduplicationSet, image: Image
) -> None:
    image_count = Image.objects.filter(deduplication_set=deduplication_set).count()
    response = another_system_api_client.delete(reverse(BULK_IMAGE_CLEAR_VIEW, (deduplication_set.pk,)))
    assert response.status_code == status.HTTP_403_FORBIDDEN
    assert Image.objects.filter(deduplication_set=deduplication_set).count() == image_count


def test_deduplication_set_is_updated(
    api_client: APIClient, user: User, deduplication_set: DeduplicationSet, image: Image
) -> None:
    assert deduplication_set.updated_by is None
    response = api_client.delete(reverse(BULK_IMAGE_CLEAR_VIEW, (deduplication_set.pk,)))
    assert response.status_code == status.HTTP_204_NO_CONTENT
    deduplication_set.refresh_from_db()
    assert deduplication_set.updated_by == user

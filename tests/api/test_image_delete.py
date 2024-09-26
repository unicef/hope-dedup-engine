from unittest.mock import MagicMock

from api_const import IMAGE_DETAIL_VIEW
from rest_framework import status
from rest_framework.reverse import reverse
from rest_framework.test import APIClient

from hope_dedup_engine.apps.api.models.deduplication import DeduplicationSet, Image
from hope_dedup_engine.apps.security.models import User


def test_can_delete_image(
    api_client: APIClient,
    deduplication_set: DeduplicationSet,
    image: Image,
    requests_get_mock: MagicMock,
) -> None:
    image_count = Image.objects.filter(deduplication_set=deduplication_set).count()
    assert deduplication_set.state == DeduplicationSet.State.CLEAN
    response = api_client.delete(
        reverse(IMAGE_DETAIL_VIEW, (deduplication_set.pk, image.pk))
    )
    assert response.status_code == status.HTTP_204_NO_CONTENT
    assert (
        Image.objects.filter(deduplication_set=deduplication_set).count()
        == image_count - 1
    )

    deduplication_set.refresh_from_db()
    assert deduplication_set.state == DeduplicationSet.State.DIRTY


def test_cannot_delete_image_between_systems(
    another_system_api_client: APIClient,
    deduplication_set: DeduplicationSet,
    image: Image,
) -> None:
    image_count = Image.objects.filter(deduplication_set=deduplication_set).count()
    response = another_system_api_client.delete(
        reverse(IMAGE_DETAIL_VIEW, (deduplication_set.pk, image.pk))
    )
    assert response.status_code == status.HTTP_403_FORBIDDEN
    assert (
        Image.objects.filter(deduplication_set=deduplication_set).count() == image_count
    )


def test_deduplication_set_is_updated(
    api_client: APIClient,
    user: User,
    deduplication_set: DeduplicationSet,
    image: Image,
    requests_get_mock: MagicMock,
) -> None:
    assert deduplication_set.updated_by is None
    response = api_client.delete(
        reverse(IMAGE_DETAIL_VIEW, (deduplication_set.pk, image.pk))
    )
    assert response.status_code == status.HTTP_204_NO_CONTENT
    deduplication_set.refresh_from_db()
    assert deduplication_set.updated_by == user

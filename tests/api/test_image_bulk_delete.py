from rest_framework import status
from rest_framework.reverse import reverse
from rest_framework.test import APIClient

from api.api_const import BULK_IMAGE_CLEAR_VIEW
from hope_dedup_engine.apps.api.models import DeduplicationSet
from hope_dedup_engine.apps.api.models.deduplication import Encoding
from hope_dedup_engine.apps.security.models import User


def test_can_delete_all_images(api_client: APIClient, deduplication_set: DeduplicationSet, encoding: Encoding) -> None:
    image_count = Encoding.objects.filter(deduplication_set=deduplication_set).count()
    response = api_client.delete(reverse(BULK_IMAGE_CLEAR_VIEW, kwargs={"deduplication_set_pk": deduplication_set.pk}))
    assert response.status_code == status.HTTP_204_NO_CONTENT
    assert Encoding.objects.filter(deduplication_set=deduplication_set).count() == image_count - 1


def test_deduplication_set_is_updated(
    api_client: APIClient, user: User, deduplication_set: DeduplicationSet, encoding: Encoding
) -> None:
    assert deduplication_set.updated_by is None
    response = api_client.delete(reverse(BULK_IMAGE_CLEAR_VIEW, kwargs={"deduplication_set_pk": deduplication_set.pk}))
    assert response.status_code == status.HTTP_204_NO_CONTENT
    deduplication_set.refresh_from_db()
    assert deduplication_set.updated_by == user

from rest_framework import status
from rest_framework.reverse import reverse
from rest_framework.test import APIClient

from api.api_const import ENCODING_DETAIL_VIEW
from hope_dedup_engine.apps.api.models.deduplication import DeduplicationSet, Encoding
from hope_dedup_engine.apps.security.models import User


def test_can_delete_encoding(
    api_client: APIClient,
    deduplication_set: DeduplicationSet,
    encoding: Encoding,
) -> None:
    encoding_count = Encoding.objects.filter(deduplication_set=deduplication_set).count()
    assert deduplication_set.state == DeduplicationSet.State.READY
    response = api_client.delete(reverse(ENCODING_DETAIL_VIEW, (deduplication_set.group.reference_pk, encoding.pk)))
    assert response.status_code == status.HTTP_204_NO_CONTENT
    assert Encoding.objects.filter(deduplication_set=deduplication_set).count() == encoding_count - 1

    deduplication_set.refresh_from_db()
    assert deduplication_set.state == DeduplicationSet.State.MODIFIED


def test_cannot_delete_encoding_between_systems(
    another_system_api_client: APIClient,
    deduplication_set: DeduplicationSet,
    encoding: Encoding,
) -> None:
    encoding_count = Encoding.objects.filter(deduplication_set=deduplication_set).count()
    response = another_system_api_client.delete(
        reverse(ENCODING_DETAIL_VIEW, (deduplication_set.group.reference_pk, encoding.pk))
    )
    assert response.status_code == status.HTTP_403_FORBIDDEN
    assert Encoding.objects.filter(deduplication_set=deduplication_set).count() == encoding_count


def test_deduplication_set_is_updated(
    api_client: APIClient,
    user: User,
    deduplication_set: DeduplicationSet,
    encoding: Encoding,
) -> None:
    assert deduplication_set.updated_by is None
    response = api_client.delete(reverse(ENCODING_DETAIL_VIEW, (deduplication_set.group.reference_pk, encoding.pk)))
    assert response.status_code == status.HTTP_204_NO_CONTENT
    deduplication_set.refresh_from_db()
    assert deduplication_set.updated_by == user

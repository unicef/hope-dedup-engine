from rest_framework import status
from rest_framework.reverse import reverse
from rest_framework.test import APIClient

from api.api_const import GROUP_DETAIL_VIEW
from hope_dedup_engine.apps.api.models import DeduplicationSet


def group_url(reference_pk: str) -> str:
    return reverse(GROUP_DETAIL_VIEW, kwargs={"reference_pk": reference_pk})


def test_can_soft_delete_group(api_client: APIClient, deduplication_set: DeduplicationSet) -> None:
    group = deduplication_set.group

    response = api_client.delete(group_url(group.reference_pk))

    assert response.status_code == status.HTTP_204_NO_CONTENT
    group.refresh_from_db()
    deduplication_set.refresh_from_db()
    assert group.deleted is True


def test_delete_group_is_idempotent(api_client: APIClient, deduplication_set_group_factory) -> None:
    group = deduplication_set_group_factory()

    assert api_client.delete(group_url(group.reference_pk)).status_code == status.HTTP_204_NO_CONTENT
    assert api_client.delete(group_url(group.reference_pk)).status_code == status.HTTP_204_NO_CONTENT


def test_delete_nonexistent_group(api_client: APIClient) -> None:
    response = api_client.delete(group_url("nonexistent-group"))

    assert response.status_code == status.HTTP_204_NO_CONTENT


def test_cannot_delete_processing_group(api_client: APIClient, deduplication_set_group_factory) -> None:
    group = deduplication_set_group_factory(processing_locked=True)

    response = api_client.delete(group_url(group.reference_pk))

    assert response.status_code == status.HTTP_409_CONFLICT
    assert response.json()["detail"] == "Cannot delete group while processing is running."
    group.refresh_from_db()
    assert group.deleted is False

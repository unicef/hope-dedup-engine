from rest_framework import status
from rest_framework.reverse import reverse
from rest_framework.test import APIClient

from api.api_const import GROUP_DETAIL_VIEW
from hope_dedup_engine.apps.api.deduplication.exceptions import GroupDeleteError
from hope_dedup_engine.apps.api.models import DeduplicationSet


def group_url(reference_pk: str) -> str:
    return reverse(GROUP_DETAIL_VIEW, kwargs={"reference_pk": reference_pk})


def test_can_soft_delete_group(api_client: APIClient, deduplication_set: DeduplicationSet) -> None:
    group = deduplication_set.group

    response = api_client.delete(group_url(group.reference_pk))

    assert response.status_code == status.HTTP_204_NO_CONTENT
    group.refresh_from_db()
    assert group.deleted is True
    assert DeduplicationSet.objects.filter(pk=deduplication_set.pk).exists()


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
    assert response.json()["detail"] == GroupDeleteError.message
    group.refresh_from_db()
    assert group.deleted is False


def test_delete_targets_active_group_when_deleted_group_with_same_reference_exists(
    api_client: APIClient,
    deduplication_set_group_factory,
) -> None:
    reference_pk = "same-ref"
    deduplication_set_group_factory(reference_pk=reference_pk, deleted=True)
    active_group = deduplication_set_group_factory(reference_pk=reference_pk)

    response = api_client.delete(group_url(reference_pk))

    assert response.status_code == status.HTTP_204_NO_CONTENT
    active_group.refresh_from_db()
    assert active_group.deleted is True

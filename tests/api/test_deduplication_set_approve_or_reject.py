from rest_framework import status
from rest_framework.reverse import reverse
from rest_framework.test import APIClient

from api.api_const import DEDUPLICATION_SET_APPROVE_VIEW, DEDUPLICATION_SET_DETAIL_VIEW, DEDUPLICATION_SET_REJECT_VIEW
from hope_dedup_engine.apps.api.models import DeduplicationSet


def test_approve_success(
    api_client: APIClient,
    deduplication_set: DeduplicationSet,
) -> None:
    deduplication_set.state = DeduplicationSet.State.DEDUPLICATED
    deduplication_set.save(update_fields=["state"])

    response = api_client.post(
        reverse(DEDUPLICATION_SET_APPROVE_VIEW, (deduplication_set.pk,)),
    )
    assert response.status_code == status.HTTP_200_OK
    deduplication_set.refresh_from_db()
    assert deduplication_set.state == DeduplicationSet.State.APPROVED


def test_approve_fails_when_not_deduplicated(
    api_client: APIClient,
    deduplication_set: DeduplicationSet,
) -> None:
    response = api_client.post(
        reverse(DEDUPLICATION_SET_APPROVE_VIEW, (deduplication_set.pk,)),
    )
    assert response.status_code == status.HTTP_409_CONFLICT


def test_reject_success(
    api_client: APIClient,
    deduplication_set: DeduplicationSet,
) -> None:
    deduplication_set.state = DeduplicationSet.State.DEDUPLICATED
    deduplication_set.save(update_fields=["state"])

    response = api_client.post(
        reverse(DEDUPLICATION_SET_REJECT_VIEW, (deduplication_set.pk,)),
    )
    assert response.status_code == status.HTTP_200_OK
    deduplication_set.refresh_from_db()
    assert deduplication_set.state == DeduplicationSet.State.REJECTED


def test_reject_fails_when_not_deduplicated(
    api_client: APIClient,
    deduplication_set: DeduplicationSet,
) -> None:
    response = api_client.post(
        reverse(DEDUPLICATION_SET_REJECT_VIEW, (deduplication_set.pk,)),
    )
    assert response.status_code == status.HTTP_409_CONFLICT


def test_approved_set_not_visible_in_api(
    api_client: APIClient,
    deduplication_set: DeduplicationSet,
) -> None:
    deduplication_set.state = DeduplicationSet.State.APPROVED
    deduplication_set.save(update_fields=["state"])

    response = api_client.get(reverse(DEDUPLICATION_SET_DETAIL_VIEW, (deduplication_set.pk,)))
    assert response.status_code == status.HTTP_404_NOT_FOUND

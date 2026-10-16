from datetime import timedelta

import pytest
from django.utils import timezone
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


@pytest.mark.parametrize(
    ("view_name", "expected_state"),
    [
        (DEDUPLICATION_SET_APPROVE_VIEW, DeduplicationSet.State.APPROVED),
        (DEDUPLICATION_SET_REJECT_VIEW, DeduplicationSet.State.REJECTED),
    ],
)
def test_approve_and_reject_refresh_updated_at(
    api_client: APIClient,
    deduplication_set: DeduplicationSet,
    view_name: str,
    expected_state: DeduplicationSet.State,
) -> None:
    previous_updated_at = timezone.now() - timedelta(days=90)
    DeduplicationSet.objects.filter(pk=deduplication_set.pk).update(
        state=DeduplicationSet.State.DEDUPLICATED,
        updated_at=previous_updated_at,
    )

    response = api_client.post(reverse(view_name, (deduplication_set.pk,)))

    assert response.status_code == status.HTTP_200_OK
    deduplication_set.refresh_from_db()
    assert deduplication_set.state == expected_state
    assert deduplication_set.updated_at > previous_updated_at


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

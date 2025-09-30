from collections.abc import Callable
from operator import attrgetter
from urllib.parse import urlencode
from datetime import timedelta
from factory.fuzzy import FuzzyText
import pytest
from rest_framework import status
from rest_framework.reverse import reverse
from rest_framework.test import APIClient

from api.api_const import DUPLICATE_LIST_VIEW
from hope_dedup_engine.apps.api.models import DeduplicationSet
from hope_dedup_engine.apps.api.models.deduplication import Finding


REFERENCE_PK = "reference_pk"
UPDATED_AFTER = "updated_after"
UPDATED_BEFORE = "updated_before"


def test_can_list_duplicates(api_client: APIClient, deduplication_set: DeduplicationSet, finding: Finding) -> None:
    response = api_client.get(reverse(DUPLICATE_LIST_VIEW, (deduplication_set.pk,)))
    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert len(data) == 1


def test_cannot_list_duplicates_between_systems(
    another_system_api_client: APIClient,
    deduplication_set: DeduplicationSet,
    finding: Finding,
) -> None:
    assert DeduplicationSet.objects.count()
    response = another_system_api_client.get(reverse(DUPLICATE_LIST_VIEW, (deduplication_set.pk,)))
    assert response.status_code == status.HTTP_403_FORBIDDEN


@pytest.mark.parametrize(
    ("filter_value_getter", "expected_amount"),
    [
        # filter by first_reference_pk
        (attrgetter("first_reference_pk"), 1),
        # filter by second_reference_pk
        (attrgetter("second_reference_pk"), 1),
        # filter by random string
        (lambda _: FuzzyText().fuzz(), 0),
    ],
)
def test_can_filter_by_reference_pk(
    api_client: APIClient,
    deduplication_set: DeduplicationSet,
    finding: Finding,
    filter_value_getter: Callable[[Finding], str],
    expected_amount: int,
) -> None:
    url = f"{reverse(DUPLICATE_LIST_VIEW, (deduplication_set.pk,))}?" + urlencode(
        {REFERENCE_PK: filter_value_getter(finding)}
    )
    response = api_client.get(url)
    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert len(data) == expected_amount


@pytest.mark.parametrize(
    ("delta_hours", "filter_param", "expected"),
    [
        (-1, UPDATED_AFTER, 1),
        (1, UPDATED_AFTER, 0),
        (1, UPDATED_BEFORE, 1),
        (-1, UPDATED_BEFORE, 0),
    ],
)
def test_filter_by_datetime(
    api_client: APIClient,
    deduplication_set: DeduplicationSet,
    finding: Finding,
    delta_hours: int,
    filter_param: str,
    expected: int,
) -> None:
    dt = (finding.updated_at + timedelta(hours=delta_hours)).isoformat()
    url = f"{reverse(DUPLICATE_LIST_VIEW, (deduplication_set.pk,))}?{urlencode({filter_param: dt})}"
    response = api_client.get(url)
    assert response.status_code == status.HTTP_200_OK
    assert len(response.json()) == expected


def test_filter_by_date_range(
    api_client: APIClient,
    deduplication_set: DeduplicationSet,
    finding: Finding,
) -> None:
    params = {
        UPDATED_AFTER: (finding.updated_at - timedelta(hours=1)).isoformat(),
        UPDATED_BEFORE: (finding.updated_at + timedelta(hours=1)).isoformat(),
    }
    url = f"{reverse(DUPLICATE_LIST_VIEW, (deduplication_set.pk,))}?{urlencode(params)}"
    response = api_client.get(url)
    assert response.status_code == status.HTTP_200_OK
    assert len(response.json()) == 1


def test_invalid_datetime_returns_400(api_client: APIClient, deduplication_set: DeduplicationSet) -> None:
    url = f"{reverse(DUPLICATE_LIST_VIEW, (deduplication_set.pk,))}?{urlencode({UPDATED_AFTER: 'invalid'})}"
    response = api_client.get(url)
    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert UPDATED_AFTER in response.json()

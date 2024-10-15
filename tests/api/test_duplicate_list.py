from collections.abc import Callable
from operator import attrgetter
from urllib.parse import urlencode

from api_const import DUPLICATE_LIST_VIEW
from factory.fuzzy import FuzzyText
from pytest import mark
from rest_framework import status
from rest_framework.reverse import reverse
from rest_framework.test import APIClient

from hope_dedup_engine.apps.api.models import DeduplicationSet
from hope_dedup_engine.apps.api.models.deduplication import Duplicate
from hope_dedup_engine.apps.api.views import REFERENCE_PK


def test_can_list_duplicates(
    api_client: APIClient, deduplication_set: DeduplicationSet, duplicate: Duplicate
) -> None:
    response = api_client.get(reverse(DUPLICATE_LIST_VIEW, (deduplication_set.pk,)))
    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert len(data) == 1


def test_cannot_list_duplicates_between_systems(
    another_system_api_client: APIClient,
    deduplication_set: DeduplicationSet,
    duplicate: Duplicate,
) -> None:
    assert DeduplicationSet.objects.count()
    response = another_system_api_client.get(
        reverse(DUPLICATE_LIST_VIEW, (deduplication_set.pk,))
    )
    assert response.status_code == status.HTTP_403_FORBIDDEN


@mark.parametrize(
    ("filter_value_getter", "expected_amount"),
    (
        # filter by first_reference_pk
        (attrgetter("first_reference_pk"), 1),
        # filter by second_reference_pk
        (attrgetter("second_reference_pk"), 1),
        # filter by random string
        (lambda _: FuzzyText().fuzz(), 0),
    ),
)
def test_can_filter_by_reference_pk(
    api_client: APIClient,
    deduplication_set: DeduplicationSet,
    duplicate: Duplicate,
    filter_value_getter: Callable[[Duplicate], str],
    expected_amount: int,
) -> None:
    url = f"{reverse(DUPLICATE_LIST_VIEW, (deduplication_set.pk, ))}?" + urlencode(
        {REFERENCE_PK: filter_value_getter(duplicate)}
    )
    response = api_client.get(url)
    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert len(data) == expected_amount

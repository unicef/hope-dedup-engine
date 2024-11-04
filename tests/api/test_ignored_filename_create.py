from api_const import IGNORED_FILENAME_LIST_VIEW, JSON
from pytest import mark
from rest_framework import status
from rest_framework.reverse import reverse
from rest_framework.test import APIClient
from testutils.factories.api import IgnoredFilenamePairFactory

from hope_dedup_engine.apps.api.models import DeduplicationSet
from hope_dedup_engine.apps.api.models.deduplication import IgnoredFilenamePair
from hope_dedup_engine.apps.api.serializers import IgnoredFilenamePairSerializer
from hope_dedup_engine.apps.security.models import User


def test_can_create_ignored_filename_pair(
    api_client: APIClient, deduplication_set: DeduplicationSet
) -> None:
    previous_amount = IgnoredFilenamePair.objects.filter(
        deduplication_set=deduplication_set
    ).count()
    data = IgnoredFilenamePairSerializer(IgnoredFilenamePairFactory.build()).data

    response = api_client.post(
        reverse(IGNORED_FILENAME_LIST_VIEW, (deduplication_set.pk,)),
        data=data,
        format=JSON,
    )
    assert response.status_code == status.HTTP_201_CREATED
    assert (
        IgnoredFilenamePair.objects.filter(deduplication_set=deduplication_set).count()
        == previous_amount + 1
    )


def test_cannot_create_ignored_filename_pair_between_systems(
    another_system_api_client: APIClient, deduplication_set: DeduplicationSet
) -> None:
    previous_amount = IgnoredFilenamePair.objects.filter(
        deduplication_set=deduplication_set
    ).count()
    data = IgnoredFilenamePairSerializer(IgnoredFilenamePairFactory.build()).data

    response = another_system_api_client.post(
        reverse(IGNORED_FILENAME_LIST_VIEW, (deduplication_set.pk,)),
        data=data,
        format=JSON,
    )
    assert response.status_code == status.HTTP_403_FORBIDDEN
    assert (
        IgnoredFilenamePair.objects.filter(deduplication_set=deduplication_set).count()
        == previous_amount
    )


INVALID_FILENAME_VALUES = "", None


@mark.parametrize("first_filename", INVALID_FILENAME_VALUES)
@mark.parametrize("second_filename", INVALID_FILENAME_VALUES)
def test_invalid_values_handling(
    api_client: APIClient,
    deduplication_set: DeduplicationSet,
    first_filename: str | None,
    second_filename: str | None,
) -> None:
    data = IgnoredFilenamePairSerializer(IgnoredFilenamePairFactory.build()).data
    data["first"] = first_filename
    data["second"] = second_filename
    response = api_client.post(
        reverse(IGNORED_FILENAME_LIST_VIEW, (deduplication_set.pk,)),
        data=data,
        format=JSON,
    )
    assert response.status_code == status.HTTP_400_BAD_REQUEST
    errors = response.json()
    assert len(errors) == 2
    assert "first" in errors
    assert "second" in errors


def test_missing_filename_handling(
    api_client: APIClient, deduplication_set: DeduplicationSet
) -> None:
    data = IgnoredFilenamePairSerializer(IgnoredFilenamePairFactory.build()).data
    del data["first"], data["second"]

    response = api_client.post(
        reverse(IGNORED_FILENAME_LIST_VIEW, (deduplication_set.pk,)),
        data=data,
        format=JSON,
    )
    assert response.status_code == status.HTTP_400_BAD_REQUEST
    errors = response.json()
    assert "first" in errors
    assert "second" in errors


def test_deduplication_set_is_updated(
    api_client: APIClient, user: User, deduplication_set: DeduplicationSet
) -> None:
    assert deduplication_set.updated_by is None

    data = IgnoredFilenamePairSerializer(IgnoredFilenamePairFactory.build()).data
    response = api_client.post(
        reverse(IGNORED_FILENAME_LIST_VIEW, (deduplication_set.pk,)),
        data=data,
        format=JSON,
    )

    assert response.status_code == status.HTTP_201_CREATED
    deduplication_set.refresh_from_db()
    assert deduplication_set.updated_by == user

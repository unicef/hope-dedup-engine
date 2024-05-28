from api_const import IGNORED_KEYS_LIST_VIEW, JSON
from pytest import mark
from rest_framework import status
from rest_framework.reverse import reverse
from rest_framework.test import APIClient
from testutils.factories.api import IgnoredKeyPairFactory

from hope_dedup_engine.apps.api.models import DeduplicationSet
from hope_dedup_engine.apps.api.models.deduplication import IgnoredKeyPair
from hope_dedup_engine.apps.api.serializers import IgnoredKeyPairSerializer
from hope_dedup_engine.apps.security.models import User


def test_can_create_ignored_key_pair(api_client: APIClient, deduplication_set: DeduplicationSet) -> None:
    previous_amount = IgnoredKeyPair.objects.filter(deduplication_set=deduplication_set).count()
    data = IgnoredKeyPairSerializer(IgnoredKeyPairFactory.build()).data

    response = api_client.post(reverse(IGNORED_KEYS_LIST_VIEW, (deduplication_set.pk,)), data=data, format=JSON)
    assert response.status_code == status.HTTP_201_CREATED
    assert IgnoredKeyPair.objects.filter(deduplication_set=deduplication_set).count() == previous_amount + 1


def test_cannot_create_ignored_key_pair_between_systems(
    another_system_api_client: APIClient, deduplication_set: DeduplicationSet
) -> None:
    previous_amount = IgnoredKeyPair.objects.filter(deduplication_set=deduplication_set).count()
    data = IgnoredKeyPairSerializer(IgnoredKeyPairFactory.build()).data

    response = another_system_api_client.post(
        reverse(IGNORED_KEYS_LIST_VIEW, (deduplication_set.pk,)), data=data, format=JSON
    )
    assert response.status_code == status.HTTP_403_FORBIDDEN
    assert IgnoredKeyPair.objects.filter(deduplication_set=deduplication_set).count() == previous_amount


INVALID_PK_VALUES = "", None


@mark.parametrize("first_pk", INVALID_PK_VALUES)
@mark.parametrize("second_pk", INVALID_PK_VALUES)
def test_invalid_values_handling(
    api_client: APIClient, deduplication_set: DeduplicationSet, first_pk: str | None, second_pk: str | None
) -> None:
    data = IgnoredKeyPairSerializer(IgnoredKeyPairFactory.build()).data
    data["first_reference_pk"] = first_pk
    data["second_reference_pk"] = second_pk
    response = api_client.post(reverse(IGNORED_KEYS_LIST_VIEW, (deduplication_set.pk,)), data=data, format=JSON)
    assert response.status_code == status.HTTP_400_BAD_REQUEST
    errors = response.json()
    assert len(errors) == 2
    assert "first_reference_pk" in errors
    assert "second_reference_pk" in errors


def test_missing_pk_handling(api_client: APIClient, deduplication_set: DeduplicationSet) -> None:
    data = IgnoredKeyPairSerializer(IgnoredKeyPairFactory.build()).data
    del data["first_reference_pk"], data["second_reference_pk"]

    response = api_client.post(reverse(IGNORED_KEYS_LIST_VIEW, (deduplication_set.pk,)), data=data, format=JSON)
    assert response.status_code == status.HTTP_400_BAD_REQUEST
    errors = response.json()
    assert "first_reference_pk" in errors
    assert "second_reference_pk" in errors


def test_deduplication_set_is_updated(api_client: APIClient, user: User, deduplication_set: DeduplicationSet) -> None:
    assert deduplication_set.updated_by is None

    data = IgnoredKeyPairSerializer(IgnoredKeyPairFactory.build()).data
    response = api_client.post(reverse(IGNORED_KEYS_LIST_VIEW, (deduplication_set.pk,)), data=data, format=JSON)

    assert response.status_code == status.HTTP_201_CREATED
    deduplication_set.refresh_from_db()
    assert deduplication_set.updated_by == user

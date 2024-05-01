from enum import StrEnum, auto
from typing import Any

from pytest import mark
from rest_framework import status
from rest_framework.reverse import reverse
from rest_framework.test import APIClient

from hope_dedup_engine.apps.public_api.serializers import DeduplicationSetSerializer
from hope_dedup_engine.apps.public_api.urls import DEDUPLICATION_SET
from testutils.factories.api import DeduplicationSetFactory


class Methods(StrEnum):
    GET = auto()
    POST = auto()


DEDUPLICATION_SET_LIST = f"{DEDUPLICATION_SET}-list"


@mark.parametrize(
    ("view_name", "method"),
    (
        (DEDUPLICATION_SET_LIST, Methods.GET),
        (DEDUPLICATION_SET_LIST, Methods.POST),
    ),
)
def test_anonymous_cannot_access(anonymous_api_client: APIClient, view_name: str, method: Methods) -> None:
    response = getattr(anonymous_api_client, method)(reverse(view_name))
    assert response.status_code == status.HTTP_401_UNAUTHORIZED


@mark.parametrize(
    ("view_name", "method", "data"),
    (
        (DEDUPLICATION_SET_LIST, Methods.GET, None),
        (DEDUPLICATION_SET_LIST, Methods.POST, DeduplicationSetSerializer(DeduplicationSetFactory.build()).data),
    ),
)
def test_authenticated_can_access(
    authenticated_api_client: APIClient, view_name: str, method: Methods, data: Any | None
) -> None:
    response = getattr(authenticated_api_client, method)(reverse("deduplication_set-list"), data=data, format="json")
    assert response.status_code in (status.HTTP_200_OK, status.HTTP_201_CREATED)

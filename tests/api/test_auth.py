from enum import StrEnum, auto
from typing import Any

from const import BULK_IMAGE_LIST_VIEW, DEDUPLICATION_SET_DETAIL_VIEW, DEDUPLICATION_SET_LIST_VIEW, IMAGE_LIST_VIEW
from conftest import get_auth_headers
from pytest import mark
from rest_framework import status
from rest_framework.reverse import reverse
from rest_framework.test import APIClient

from hope_dedup_engine.apps.security.models import User
from testutils.factories.api import TokenFactory


class Methods(StrEnum):
    GET = auto()
    POST = auto()
    DELETE = auto()


PK = 1


@mark.parametrize(
    ("view_name", "method", "args"),
    (
        (DEDUPLICATION_SET_LIST_VIEW, Methods.GET, ()),
        (DEDUPLICATION_SET_LIST_VIEW, Methods.POST, ()),
        (DEDUPLICATION_SET_DETAIL_VIEW, Methods.DELETE, (PK,)),
        (IMAGE_LIST_VIEW, Methods.GET, (PK,)),
        (IMAGE_LIST_VIEW, Methods.POST, (PK,)),
        (BULK_IMAGE_LIST_VIEW, Methods.POST, (PK,)),
    ),
)
def test_anonymous_cannot_access(
    anonymous_api_client: APIClient, view_name: str, method: Methods, args: tuple[Any, ...]
) -> None:
    response = getattr(anonymous_api_client, method)(reverse(view_name, args))
    assert response.status_code == status.HTTP_401_UNAUTHORIZED


@mark.parametrize(
    ("view_name", "method", "args"),
    (
        (DEDUPLICATION_SET_LIST_VIEW, Methods.GET, ()),
        (DEDUPLICATION_SET_LIST_VIEW, Methods.POST, ()),
        (DEDUPLICATION_SET_DETAIL_VIEW, Methods.DELETE, (PK,)),
        (IMAGE_LIST_VIEW, Methods.GET, (PK,)),
        (IMAGE_LIST_VIEW, Methods.POST, (PK,)),
        (BULK_IMAGE_LIST_VIEW, Methods.POST, (PK,)),
    ),
)
def test_authenticated_can_access(
    api_client: APIClient, view_name: str, method: Methods, args: tuple[Any, ...]
) -> None:
    response = getattr(api_client, method)(reverse(view_name, args), format="json")
    assert response.status_code != status.HTTP_401_UNAUTHORIZED


def test_multiple_tokens_can_be_used(api_client: APIClient, user: User) -> None:
    tokens = [TokenFactory(user=user) for _ in range(5)]
    for token in tokens:
        api_client.credentials(**get_auth_headers(token))
        response = api_client.get(reverse(DEDUPLICATION_SET_LIST_VIEW))
        assert response.status_code == status.HTTP_200_OK

from http import HTTPMethod
from typing import Any
from uuid import uuid4

from api_const import (
    BULK_IMAGE_CLEAR_VIEW,
    BULK_IMAGE_LIST_VIEW,
    DEDUPLICATION_SET_DETAIL_VIEW,
    DEDUPLICATION_SET_LIST_VIEW,
    IGNORED_REFERENCE_PK_LIST_VIEW,
    IMAGE_DETAIL_VIEW,
    IMAGE_LIST_VIEW,
    JSON,
)
from conftest import get_auth_headers
from pytest import mark
from rest_framework import status
from rest_framework.reverse import reverse
from rest_framework.test import APIClient
from testutils.factories.api import TokenFactory

from hope_dedup_engine.apps.security.models import User

PK = uuid4()


REQUESTS = (
    (DEDUPLICATION_SET_LIST_VIEW, HTTPMethod.GET, ()),
    (DEDUPLICATION_SET_LIST_VIEW, HTTPMethod.POST, ()),
    (DEDUPLICATION_SET_DETAIL_VIEW, HTTPMethod.DELETE, (PK,)),
    (IMAGE_LIST_VIEW, HTTPMethod.GET, (PK,)),
    (IMAGE_LIST_VIEW, HTTPMethod.POST, (PK,)),
    (BULK_IMAGE_LIST_VIEW, HTTPMethod.POST, (PK,)),
    (IMAGE_DETAIL_VIEW, HTTPMethod.DELETE, (PK, PK)),
    (BULK_IMAGE_CLEAR_VIEW, HTTPMethod.DELETE, (PK,)),
    (IGNORED_REFERENCE_PK_LIST_VIEW, HTTPMethod.GET, (PK,)),
    (IGNORED_REFERENCE_PK_LIST_VIEW, HTTPMethod.POST, (PK,)),
)


@mark.parametrize(("view_name", "method", "args"), REQUESTS)
def test_anonymous_cannot_access(
    anonymous_api_client: APIClient,
    view_name: str,
    method: HTTPMethod,
    args: tuple[Any, ...],
) -> None:
    response = getattr(anonymous_api_client, method.lower())(reverse(view_name, args))
    assert response.status_code == status.HTTP_401_UNAUTHORIZED


@mark.parametrize(("view_name", "method", "args"), REQUESTS)
def test_authenticated_can_access(
    api_client: APIClient, view_name: str, method: HTTPMethod, args: tuple[Any, ...]
) -> None:
    response = getattr(api_client, method.lower())(
        reverse(view_name, args), format=JSON
    )
    assert response.status_code != status.HTTP_401_UNAUTHORIZED


def test_multiple_tokens_can_be_used(api_client: APIClient, user: User) -> None:
    tokens = [TokenFactory(user=user) for _ in range(5)]
    for token in tokens:
        api_client.credentials(**get_auth_headers(token))
        response = api_client.get(reverse(DEDUPLICATION_SET_LIST_VIEW))
        assert response.status_code == status.HTTP_200_OK

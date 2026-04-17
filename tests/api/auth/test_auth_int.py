from http import HTTPMethod
from typing import Any

import pytest
from rest_framework import status
from rest_framework.reverse import reverse
from rest_framework.test import APIClient
from testutils.factories.api import HDETokenFactory
from testutils.factories.user import UserFactory, SystemFactory

from hope_dedup_engine.apps.api.models import HDEToken, DeduplicationSet
from hope_dedup_engine.apps.security.models import User, System
from api.api_const import (
    BULK_IMAGE_CLEAR_VIEW,
    BULK_IMAGE_LIST_VIEW,
    DEDUPLICATION_SET_DETAIL_VIEW,
    DEDUPLICATION_SET_LIST_VIEW,
    JSON,
)
from api.utils import get_auth_headers

PK = object()


REQUESTS = (
    (DEDUPLICATION_SET_LIST_VIEW, HTTPMethod.GET, ()),
    (DEDUPLICATION_SET_LIST_VIEW, HTTPMethod.POST, ()),
    (DEDUPLICATION_SET_DETAIL_VIEW, HTTPMethod.DELETE, (PK,)),
    (BULK_IMAGE_LIST_VIEW, HTTPMethod.POST, (PK,)),
    (BULK_IMAGE_CLEAR_VIEW, HTTPMethod.DELETE, (PK,)),
)


def preprocess_args(deduplication_set: DeduplicationSet, args: tuple[Any, ...]) -> tuple[Any, ...]:
    return tuple(str(deduplication_set.pk) if arg == PK else arg for arg in args)


def preprocess_kwargs(deduplication_set: DeduplicationSet, args: tuple[Any, ...]) -> dict[str, Any]:
    """For nested routes that use kwargs instead of positional args."""
    return {}


@pytest.mark.parametrize(("view_name", "method", "args"), REQUESTS)
def test_anonymous_cannot_access(
    anonymous_api_client: APIClient,
    deduplication_set: DeduplicationSet,
    view_name: str,
    method: HTTPMethod,
    args: tuple[Any, ...],
) -> None:
    processed = preprocess_args(deduplication_set, args)
    if view_name in (BULK_IMAGE_LIST_VIEW, BULK_IMAGE_CLEAR_VIEW):
        url = reverse(view_name, kwargs={"deduplication_set_pk": deduplication_set.pk})
    else:
        url = reverse(view_name, processed)
    response = getattr(anonymous_api_client, method.lower())(url)
    assert response.status_code == status.HTTP_401_UNAUTHORIZED


@pytest.mark.parametrize(("view_name", "method", "args"), REQUESTS)
def test_authenticated_can_access(
    api_client: APIClient,
    deduplication_set: DeduplicationSet,
    view_name: str,
    method: HTTPMethod,
    args: tuple[Any, ...],
) -> None:
    processed = preprocess_args(deduplication_set, args)
    if view_name in (BULK_IMAGE_LIST_VIEW, BULK_IMAGE_CLEAR_VIEW):
        url = reverse(view_name, kwargs={"deduplication_set_pk": deduplication_set.pk})
    else:
        url = reverse(view_name, processed)
    response = getattr(api_client, method.lower())(url, format=JSON)
    assert response.status_code != status.HTTP_401_UNAUTHORIZED


def test_multiple_tokens_can_be_used(api_client: APIClient, user: User, system: System) -> None:
    tokens = [HDETokenFactory(user=user, system=system) for _ in range(5)]
    for token in tokens:
        api_client.credentials(**get_auth_headers(token))
        response = api_client.get(reverse(DEDUPLICATION_SET_LIST_VIEW))
        assert response.status_code == status.HTTP_200_OK


@pytest.mark.django_db
def test_hde_token_generation(api_client: APIClient):
    user = UserFactory()
    system = SystemFactory()
    token = HDEToken(user=user, system=system)
    token.save()

    assert token.key is not None
    assert len(token.key) == 40

from typing import Any
from unittest.mock import MagicMock

from pytest import fixture
from pytest_factoryboy import LazyFixture, register
from pytest_mock import MockerFixture
from rest_framework.test import APIClient
from testutils.factories.api import DeduplicationSetFactory, ImageFactory, TokenFactory
from testutils.factories.user import ExternalSystemFactory, UserFactory

from hope_dedup_engine.apps.public_api.models import HDEToken
from hope_dedup_engine.apps.security.models import User

register(ExternalSystemFactory)
register(UserFactory)
register(DeduplicationSetFactory, external_system=LazyFixture("external_system"))
register(ImageFactory, deduplication_Set=LazyFixture("deduplication_set"))


@fixture
def anonymous_api_client() -> APIClient:
    return APIClient()


def get_auth_headers(token: HDEToken) -> dict[str, str]:
    return {"HTTP_AUTHORIZATION": f"Token {token.key}"}


def create_api_client(user: User) -> APIClient:
    token = TokenFactory(user=user)
    client = APIClient()
    client.credentials(**get_auth_headers(token))
    return client


@fixture
def api_client(user: User) -> APIClient:
    return create_api_client(user)


@fixture
def another_system_api_client(db: Any) -> APIClient:
    another_system_user = UserFactory()
    return create_api_client(another_system_user)


@fixture
def delete_model_data(mocker: MockerFixture) -> MagicMock:
    return mocker.patch("hope_dedup_engine.apps.public_api.views.delete_model_data")


@fixture
def start_processing(mocker: MockerFixture) -> MagicMock:
    return mocker.patch("hope_dedup_engine.apps.public_api.views.start_processing")

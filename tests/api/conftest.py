from pytest import fixture
from pytest_factoryboy import register
from rest_framework.test import APIClient

from hope_dedup_engine.apps.public_api.models import HDEToken, DeduplicationSet
from hope_dedup_engine.apps.security.models import User
from testutils.factories.user import ExternalSystemFactory, UserFactory
from testutils.factories.api import TokenFactory, DeduplicationSetFactory

register(ExternalSystemFactory)
register(UserFactory)


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


@fixture()
def authenticated_api_client(user: User) -> APIClient:
    return create_api_client(user)


@fixture()
def deduplication_set(user: User) -> DeduplicationSet:
    return DeduplicationSetFactory(created_by=user, external_system=user.external_system)

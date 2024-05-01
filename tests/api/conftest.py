from pytest import fixture
from pytest_factoryboy import register
from rest_framework.test import APIClient

from hope_dedup_engine.apps.security.models import User
from testutils.factories import UserFactory
from testutils.factories.api import TokenFactory

register(UserFactory)


@fixture
def anonymous_api_client() -> APIClient:
    return APIClient()


@fixture()
def authenticated_api_client(user: User) -> APIClient:
    token = TokenFactory(user=user)
    client = APIClient()
    client.credentials(HTTP_AUTHORIZATION=f"Token {token.key}")
    return client

from rest_framework.test import APIClient

from hope_dedup_engine.apps.api.models import HDEToken
from hope_dedup_engine.apps.security.models import User
from testutils.factories.api import TokenFactory


def get_auth_headers(token: HDEToken) -> dict[str, str]:
    return {"HTTP_AUTHORIZATION": f"Token {token.key}"}


def create_api_client(user: User) -> APIClient:
    token = TokenFactory(user=user)
    client = APIClient()
    client.credentials(**get_auth_headers(token))
    return client

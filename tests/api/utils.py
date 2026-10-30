from rest_framework.test import APIClient

from hope_api_auth.models import APIToken


def get_auth_headers(token: APIToken) -> dict[str, str]:
    return {"HTTP_AUTHORIZATION": f"Token {token.key}"}


def create_api_client(token: APIToken) -> APIClient:
    client = APIClient()
    client.credentials(**get_auth_headers(token))
    return client

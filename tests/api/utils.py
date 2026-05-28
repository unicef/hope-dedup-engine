import base64

from rest_framework.test import APIClient

from hope_dedup_engine.apps.api.models import HDEToken


def jpeg_data_url(payload: bytes = b"fake-jpeg-bytes") -> str:
    """Minimal valid base64 data URL accepted by CreateEncodingSerializer."""
    return f"data:image/jpeg;base64,{base64.b64encode(payload).decode()}"


def get_auth_headers(token: HDEToken) -> dict[str, str]:
    return {"HTTP_AUTHORIZATION": f"Token {token.key}"}


def create_api_client(token: HDEToken) -> APIClient:
    client = APIClient()
    client.credentials(**get_auth_headers(token))
    return client

from typing import TYPE_CHECKING
from unittest import mock

import pytest

from hope_dedup_engine.state import state
from hope_dedup_engine.utils.http import (
    absolute_reverse,
    absolute_uri,
    get_server_host,
    get_server_url,
)

if TYPE_CHECKING:
    from django.http import HttpRequest
    from django.test.client import RequestFactory


@pytest.fixture(autouse=True)
def r(monkeypatch, rf: "RequestFactory"):
    req: "HttpRequest" = rf.get("/", HTTP_HOST="127.0.0.1")
    m = mock.patch("hope_dedup_engine.state.state.request", req)
    m.start()
    yield
    m.stop()


def test_absolute_reverse(settings):
    settings.SOCIAL_AUTH_REDIRECT_IS_HTTPS = False
    assert absolute_reverse("home") == "http://127.0.0.1/"


def test_absolute_uri(settings):
    settings.SOCIAL_AUTH_REDIRECT_IS_HTTPS = False
    assert absolute_uri("aa") == "http://127.0.0.1/aa"
    assert absolute_uri("") == "http://127.0.0.1/"
    settings.SOCIAL_AUTH_REDIRECT_IS_HTTPS = True
    assert absolute_uri("") == "https://127.0.0.1/"
    with state.configure(request=None):
        assert absolute_uri("") == ""
    with state.configure(request=None):
        assert absolute_uri("/test/") == "/test/"


def test_get_server_host():
    assert get_server_host() == "127.0.0.1"


def test_get_server_url(settings):
    settings.SOCIAL_AUTH_REDIRECT_IS_HTTPS = False
    assert get_server_url() == "http://127.0.0.1"
    with state.configure(request=None):
        assert get_server_url() == ""

    settings.SOCIAL_AUTH_REDIRECT_IS_HTTPS = True
    assert get_server_url() == "https://127.0.0.1"

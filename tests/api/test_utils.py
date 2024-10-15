from unittest.mock import MagicMock

from pytest import fixture, mark
from pytest_mock import MockFixture
from requests import RequestException

from hope_dedup_engine.apps.api.utils.notification import (
    REQUEST_TIMEOUT,
    send_notification,
)


@fixture
def requests_get(mocker: MockFixture) -> MagicMock:
    return mocker.patch("hope_dedup_engine.apps.api.utils.notification.requests.get")


@fixture
def sentry_sdk_capture_exception(mocker: MockFixture) -> MagicMock:
    return mocker.patch(
        "hope_dedup_engine.apps.api.utils.notification.sentry_sdk.capture_exception"
    )


@mark.parametrize(
    ("url", "http_request_sent"), (("https://example.com", True), (None, False))
)
def test_send_notification(
    url: str | None,
    http_request_sent: bool,
    requests_get: MagicMock,
) -> None:
    send_notification(url)
    if http_request_sent:
        requests_get.assert_called_once_with(url, timeout=REQUEST_TIMEOUT)
    else:
        requests_get.assert_not_called()


def test_exception_is_sent_to_sentry(
    requests_get: MagicMock, sentry_sdk_capture_exception: MagicMock
) -> None:
    exception = RequestException()
    requests_get.side_effect = exception
    send_notification("https://example.com")
    sentry_sdk_capture_exception.assert_called_once_with(exception)

from unittest.mock import MagicMock

import pytest
from pytest_mock import MockFixture
from requests import RequestException

from hope_dedup_engine.apps.api.models import DeduplicationSet
from hope_dedup_engine.apps.api.utils.notification import (
    REQUEST_TIMEOUT,
    send_notification,
)
from hope_dedup_engine.apps.api.utils.progress import callback_filter


@pytest.fixture
def requests_get(mocker: MockFixture) -> MagicMock:
    return mocker.patch("hope_dedup_engine.apps.api.utils.notification.requests.get")


@pytest.fixture
def sentry_sdk_capture_exception(mocker: MockFixture) -> MagicMock:
    return mocker.patch("hope_dedup_engine.apps.api.utils.notification.sentry_sdk.capture_exception")


@pytest.fixture
def deduplication_set_mock(mocker: MockFixture) -> MagicMock:
    return mocker.Mock(spec=DeduplicationSet)


@pytest.mark.parametrize(
    ("url", "notify", "http_request_sent"),
    [
        ("https://example.com", True, True),
        ("https://example.com", False, False),
        (None, True, False),
        (None, False, False),
    ],
)
def test_send_notification(
    url: str | None,
    notify: bool,
    http_request_sent: bool,
    requests_get: MagicMock,
    deduplication_set_mock: DeduplicationSet,
) -> None:
    deduplication_set_mock.notification_url = url
    deduplication_set_mock.notify = notify
    send_notification(deduplication_set_mock)
    if http_request_sent:
        requests_get.assert_called_once_with(url, timeout=REQUEST_TIMEOUT)
    else:
        requests_get.assert_not_called()


def test_exception_is_sent_to_sentry(
    requests_get: MagicMock, sentry_sdk_capture_exception: MagicMock, deduplication_set_mock: DeduplicationSet
) -> None:
    exception = RequestException()
    requests_get.side_effect = exception
    send_notification(deduplication_set_mock)
    sentry_sdk_capture_exception.assert_called_once_with(exception)


def test_callback_filter() -> None:
    step = 10
    values = []
    update = callback_filter(lambda x: values.append(x), step)
    for i in range(1, 101):
        update(i)
    assert values == list(range(0, 101, step))

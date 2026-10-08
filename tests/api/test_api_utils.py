from unittest.mock import MagicMock

import pytest
from pytest_mock import MockFixture
from requests import RequestException

from hope_dedup_engine.apps.api.models import DeduplicationSet
from hope_dedup_engine.apps.api.utils.notification import (
    REQUEST_RETRIES,
    REQUEST_TIMEOUT,
    RETRY_BACKOFF_FACTOR,
    RETRY_STATUSES,
    notification_session,
    send_notification,
    WarningMessage,
    ErrorMessage,
    NOTIFICATION_DISABLED,
    NO_NOTIFICATION_URL,
    FAILED_TO_NOTIFY,
)
from hope_dedup_engine.apps.api.utils.progress import callback_filter


@pytest.fixture
def requests_get(mocker: MockFixture) -> MagicMock:
    return mocker.patch("hope_dedup_engine.apps.api.utils.notification.requests.Session.get")


@pytest.fixture
def sentry_sdk_capture_exception(mocker: MockFixture) -> MagicMock:
    return mocker.patch("hope_dedup_engine.apps.api.utils.notification.sentry_sdk.capture_exception")


@pytest.fixture
def deduplication_set_mock(mocker: MockFixture) -> MagicMock:
    return mocker.Mock(spec=DeduplicationSet)


@pytest.mark.parametrize(
    ("url", "notify", "force", "expected_notification_result", "http_request_sent"),
    [
        ("https://example.com", True, False, None, True),
        ("https://example.com", True, True, None, True),
        ("https://example.com", False, False, WarningMessage(NOTIFICATION_DISABLED), False),
        ("https://example.com", False, True, None, True),
        (None, True, False, WarningMessage(NO_NOTIFICATION_URL), False),
        (None, False, True, WarningMessage(NO_NOTIFICATION_URL), False),
    ],
)
def test_send_notification(
    url: str | None,
    notify: bool,
    force: bool,
    expected_notification_result: None | WarningMessage,
    http_request_sent: bool,
    requests_get: MagicMock,
    deduplication_set_mock: DeduplicationSet,
) -> None:
    deduplication_set_mock.notification_url = url
    deduplication_set_mock.notify = notify

    notification_result = send_notification(deduplication_set_mock, force=force)

    assert notification_result == expected_notification_result

    if http_request_sent:
        requests_get.assert_called_once_with(url, timeout=REQUEST_TIMEOUT)
    else:
        requests_get.assert_not_called()


def test_send_notification_sends_no_credentials(
    requests_get: MagicMock, deduplication_set_mock: DeduplicationSet
) -> None:
    """The notification url is caller-supplied, so no headers may be attached to it."""
    deduplication_set_mock.notification_url = "https://example.com"
    deduplication_set_mock.notify = True

    send_notification(deduplication_set_mock)

    assert "headers" not in requests_get.call_args.kwargs


@pytest.mark.parametrize("scheme", ["http", "https"])
def test_notification_session_retries_transient_failures(scheme: str) -> None:
    """Transient failures are retried; permanent ones (other 4xx) are not."""
    retries = notification_session().get_adapter(f"{scheme}://example.com").max_retries

    assert retries.total == REQUEST_RETRIES
    assert retries.backoff_factor == RETRY_BACKOFF_FACTOR
    assert retries.status_forcelist == RETRY_STATUSES
    assert retries.allowed_methods == frozenset({"GET"})
    assert 404 not in retries.status_forcelist


def test_exception_is_sent_to_sentry(
    requests_get: MagicMock, sentry_sdk_capture_exception: MagicMock, deduplication_set_mock: DeduplicationSet
) -> None:
    exception = RequestException("Error")
    requests_get.side_effect = exception
    assert send_notification(deduplication_set_mock) == ErrorMessage(FAILED_TO_NOTIFY.format(error=exception))
    sentry_sdk_capture_exception.assert_called_once_with(exception)


def test_callback_filter() -> None:
    step = 10
    values = []
    update = callback_filter(lambda x: values.append(x), step)
    for i in range(1, 101):
        update(i)
    assert values == list(range(0, 101, step))

from unittest.mock import MagicMock

import pytest
from pytest_mock import MockFixture
from requests import RequestException
from constance.test import override_config

from hope_dedup_engine.apps.api.models import DeduplicationSet
from hope_dedup_engine.apps.api.utils.notification import (
    REQUEST_TIMEOUT,
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
    return mocker.patch("hope_dedup_engine.apps.api.utils.notification.requests.get")


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

    token = "very-secret-token"
    with override_config(HOPE_API_TOKEN=token):
        notification_result = send_notification(deduplication_set_mock, force=force)

    assert notification_result == expected_notification_result

    if http_request_sent:
        requests_get.assert_called_once_with(
            url,
            headers={"Authorization": f"Token {token}"},
            timeout=REQUEST_TIMEOUT,
        )
    else:
        requests_get.assert_not_called()


def test_exception_is_sent_to_sentry(
    requests_get: MagicMock, sentry_sdk_capture_exception: MagicMock, deduplication_set_mock: DeduplicationSet
) -> None:
    exception = RequestException("Error")
    requests_get.side_effect = exception
    with override_config(HOPE_API_TOKEN="any-token"):
        assert send_notification(deduplication_set_mock) == ErrorMessage(FAILED_TO_NOTIFY.format(error=exception))
    sentry_sdk_capture_exception.assert_called_once_with(exception)


def test_callback_filter() -> None:
    step = 10
    values = []
    update = callback_filter(lambda x: values.append(x), step)
    for i in range(1, 101):
        update(i)
    assert values == list(range(0, 101, step))

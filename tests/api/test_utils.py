from unittest.mock import MagicMock

from pytest import fixture, mark
from pytest_mock import MockerFixture

from hope_dedup_engine.apps.api.models import DeduplicationSet
from hope_dedup_engine.apps.api.utils import send_notification


@fixture
def requests_get_mock(mocker: MockerFixture) -> MagicMock:
    return mocker.patch("hope_dedup_engine.apps.api.utils.requests.get")


@mark.parametrize("deduplication_set__notification_url", ("https://example.com",))
def test_notification_is_sent_when_url_is_set(
    requests_get_mock: MagicMock, deduplication_set: DeduplicationSet
) -> None:
    send_notification(deduplication_set)
    requests_get_mock.assert_called_once_with(deduplication_set.notification_url)


@mark.parametrize("deduplication_set__notification_url", (None,))
def test_notification_is_not_sent_when_url_is_not_set(
    requests_get_mock: MagicMock, deduplication_set: DeduplicationSet
) -> None:
    send_notification(deduplication_set)
    requests_get_mock.assert_not_called()

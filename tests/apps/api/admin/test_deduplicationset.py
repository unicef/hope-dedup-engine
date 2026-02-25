import pytest
from django.contrib.messages import get_messages, ERROR, WARNING, SUCCESS
from django.test import Client
from django.urls import reverse
from pytest_mock import MockerFixture

from hope_dedup_engine.apps.api.admin.deduplicationset import NOTIFICATION_SENT
from hope_dedup_engine.apps.api.models import DeduplicationSet
from hope_dedup_engine.apps.api.utils.notification import WarningMessage, ErrorMessage


@pytest.mark.parametrize(
    ("notification_result", "expected_message", "expected_level"),
    [
        (None, NOTIFICATION_SENT, SUCCESS),
        (ErrorMessage(m := "Error occurred"), m, ERROR),
        (WarningMessage(m := "Something is wrong"), m, WARNING),
    ],
)
def test_send_notification_button_message(
    admin_client: Client,
    deduplication_set: DeduplicationSet,
    mocker: MockerFixture,
    notification_result: None | WarningMessage | ErrorMessage,
    expected_message: str,
    expected_level,
) -> None:
    send_notification_mock = mocker.patch(
        "hope_dedup_engine.apps.api.admin.deduplicationset.send_notification", return_value=notification_result
    )
    url = reverse("admin:api_deduplicationset_send_notification", args=[deduplication_set.pk])

    response = admin_client.get(url)
    messages = get_messages(response.wsgi_request)

    assert len(messages) == 1
    message = next(iter(messages))
    assert message.message == expected_message
    assert message.level == expected_level
    send_notification_mock.assert_called_once_with(deduplication_set, force=True)

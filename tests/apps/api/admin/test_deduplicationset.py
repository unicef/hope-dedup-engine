import pytest
from azure.core.exceptions import ResourceNotFoundError
from django.contrib.messages import get_messages, ERROR, WARNING, SUCCESS
from django.test import Client
from django.http import StreamingHttpResponse
from django.urls import reverse
from pytest_mock import MockerFixture

from hope_dedup_engine.apps.api.admin.deduplicationset import NOTIFICATION_SENT
from hope_dedup_engine.apps.api.models import DeduplicationSet
from hope_dedup_engine.apps.api.utils.notification import WarningMessage, ErrorMessage


@pytest.fixture
def img() -> object:
    return object()


@pytest.fixture
def storage(img: object, mocker: MockerFixture):
    storage = mocker.Mock()

    def load_image(name: str) -> object:
        if name == "missing.jpg":
            raise ResourceNotFoundError("missing")
        return img

    storage.load_image.side_effect = load_image
    return storage


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


@pytest.mark.parametrize(
    ("row_in", "expected"),
    [
        (("r1", "ok.jpg"), ("r1", "ok.jpg", 0.42)),
        (("r2", "bad.jpg"), ("r2", "bad.jpg", None)),
        (("r3", "missing.jpg"), ("r3", "missing.jpg", None)),
    ],
    ids=("ok", "bad_value", "missing_blob"),
)
def test_assess_quality_button(
    admin_client,
    deduplication_set,
    img,
    storage,
    row_in,
    expected,
    mocker,
) -> None:
    mocker.patch("hope_dedup_engine.apps.api.admin.deduplicationset.ImagesStorageManager", return_value=storage)

    contrast_fn = mocker.patch(
        "hope_dedup_engine.apps.api.admin.deduplicationset.michelson_contrast",
        return_value=0.42,
    )
    contrast_fn.side_effect = lambda _img: (_ for _ in ()).throw(ValueError("bad")) if row_in[1] == "bad.jpg" else 0.42

    def fake_stream_as_csv(_qs, _out, *, fields, headers=None, row_mapper=None, **_):
        assert row_mapper(row_in) == expected
        if row_in[1] == "missing.jpg":
            contrast_fn.assert_not_called()
        else:
            assert contrast_fn.call_args[0][0] is img
        return StreamingHttpResponse([])

    mocker.patch(
        "hope_dedup_engine.apps.api.admin.deduplicationset.stream_as_csv",
        side_effect=fake_stream_as_csv,
    )

    url = reverse("admin:api_deduplicationset_assess_quality", args=[deduplication_set.pk])
    assert admin_client.get(url).status_code == 200

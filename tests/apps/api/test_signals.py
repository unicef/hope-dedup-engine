from unittest.mock import Mock, patch

import pytest
from django.core.files.base import ContentFile

from hope_dedup_engine.apps.api.models import Encoding
from hope_dedup_engine.apps.api.signals import delete_encoding_image_file

pytestmark = pytest.mark.django_db


def test_delete_encoding_removes_image_file(deduplication_set, django_capture_on_commit_callbacks) -> None:
    encoding = Encoding.objects.create(
        deduplication_set=deduplication_set,
        reference_pk="ref-del",
        filename=ContentFile(b"image-bytes", name="ref-del.jpg"),
    )
    storage_path = encoding.filename.name
    storage = encoding.filename.storage
    assert storage.exists(storage_path)

    with django_capture_on_commit_callbacks(execute=True):
        encoding.delete()
        assert storage.exists(storage_path)

    assert not storage.exists(storage_path)


def test_delete_encoding_skips_missing_filename(deduplication_set) -> None:
    encoding = Encoding(deduplication_set=deduplication_set, reference_pk="ref-empty")
    assert not encoding.filename

    delete_encoding_image_file(Encoding, encoding)


def test_delete_encoding_ignores_file_not_found(django_capture_on_commit_callbacks) -> None:
    encoding = Mock()
    field = Mock()
    field.__bool__ = Mock(return_value=True)
    field.name = "images/group/set/ref.jpg"
    storage = Mock()
    storage.delete = Mock(side_effect=FileNotFoundError())
    field.storage = storage
    encoding.filename = field

    with django_capture_on_commit_callbacks(execute=True):
        delete_encoding_image_file(Encoding, encoding)

    storage.delete.assert_called_once_with("images/group/set/ref.jpg")


def test_delete_encoding_logs_unexpected_storage_errors(django_capture_on_commit_callbacks) -> None:
    encoding = Mock()
    field = Mock()
    field.__bool__ = Mock(return_value=True)
    field.name = "images/group/set/ref.jpg"
    storage = Mock()
    storage.delete = Mock(side_effect=OSError("storage unavailable"))
    field.storage = storage
    encoding.filename = field

    with (
        patch("hope_dedup_engine.apps.api.signals.logger.warning") as warning_mock,
        django_capture_on_commit_callbacks(execute=True),
    ):
        delete_encoding_image_file(Encoding, encoding)

    warning_mock.assert_called_once()

from unittest.mock import Mock, patch

import pytest
from django.core.files.base import ContentFile

from hope_dedup_engine.apps.api.models import Encoding
from hope_dedup_engine.apps.api.signals import delete_encoding_image_file

pytestmark = pytest.mark.django_db


def test_delete_encoding_removes_image_file(deduplication_set) -> None:
    encoding = Encoding.objects.create(
        deduplication_set=deduplication_set,
        reference_pk="ref-del",
        filename=ContentFile(b"image-bytes", name="ref-del.jpg"),
    )
    storage_path = encoding.filename.name
    storage = encoding.filename.storage
    assert storage.exists(storage_path)

    encoding.delete()

    assert not storage.exists(storage_path)


def test_delete_encoding_skips_missing_filename(deduplication_set) -> None:
    encoding = Encoding(deduplication_set=deduplication_set, reference_pk="ref-empty")
    assert not encoding.filename

    delete_encoding_image_file(Encoding, encoding)


def test_delete_encoding_ignores_file_not_found() -> None:
    encoding = Mock()
    field = Mock()
    field.__bool__ = Mock(return_value=True)
    field.delete = Mock(side_effect=FileNotFoundError())
    field.name = "images/group/set/ref.jpg"
    encoding.filename = field

    delete_encoding_image_file(Encoding, encoding)

    field.delete.assert_called_once_with(save=False)


def test_delete_encoding_logs_unexpected_storage_errors() -> None:
    encoding = Mock()
    field = Mock()
    field.__bool__ = Mock(return_value=True)
    field.delete = Mock(side_effect=OSError("storage unavailable"))
    field.name = "images/group/set/ref.jpg"
    encoding.filename = field

    with patch("hope_dedup_engine.apps.api.signals.logger.warning") as warning_mock:
        delete_encoding_image_file(Encoding, encoding)

    warning_mock.assert_called_once()

import cv2
import numpy as np
import pytest
from django.core.files.base import ContentFile
from django.core.files.storage import storages

from hope_dedup_engine.apps.api.exceptions import ImageDecodeError
from hope_dedup_engine.apps.api.utils.image import load_image

pytestmark = pytest.mark.django_db


def _save(key: str, content: bytes) -> None:
    storage = storages["hope"]
    if storage.exists(key):
        storage.delete(key)
    storage.save(key, ContentFile(content))


def test_load_image_decodes_png_from_hope_storage() -> None:
    source = np.zeros((8, 8, 3), dtype=np.uint8)
    source[0, 0] = (255, 0, 0)
    ok, buf = cv2.imencode(".png", source)
    assert ok

    key = "hope/img-load.png"
    _save(key, buf.tobytes())

    decoded = load_image(key)

    assert decoded.shape == (8, 8, 3)
    assert decoded[0, 0, 0] == 255


def test_load_image_raises_when_blob_is_missing() -> None:
    key = "hope/img-missing.png"
    storage = storages["hope"]
    if storage.exists(key):
        storage.delete(key)

    with pytest.raises(FileNotFoundError):
        load_image(key)


def test_load_image_raises_when_blob_is_not_an_image() -> None:
    key = "hope/img-invalid.png"
    _save(key, b"not-an-image")

    with pytest.raises(ImageDecodeError):
        load_image(key)

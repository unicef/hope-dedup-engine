import cv2
import numpy as np
import pytest
from django.core.files.base import ContentFile
from django.core.files.storage import storages

from hope_dedup_engine.apps.api.utils.image import load_image

pytestmark = pytest.mark.django_db


def test_load_image_decodes_png_from_hope_storage() -> None:
    source = np.zeros((8, 8, 3), dtype=np.uint8)
    source[0, 0] = (255, 0, 0)
    ok, buf = cv2.imencode(".png", source)
    assert ok

    key = "hope/img-load.png"
    storage = storages["hope"]
    if storage.exists(key):
        storage.delete(key)
    storage.save(key, ContentFile(buf.tobytes()))

    decoded = load_image(key)

    assert decoded.shape == (8, 8, 3)
    assert decoded[0, 0, 0] == 255

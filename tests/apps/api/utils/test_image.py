import cv2
import numpy as np
import pytest
from django.core.files.base import ContentFile

from hope_dedup_engine.apps.api.models import Encoding
from hope_dedup_engine.apps.api.utils.image import encoding_image_key, load_image

pytestmark = pytest.mark.django_db


def test_encoding_image_key() -> None:
    deduplication_set_id = "11111111-1111-1111-1111-111111111111"
    assert (
        encoding_image_key("group-a", deduplication_set_id, "ref.jpg")
        == f"images/group-a/{deduplication_set_id}/ref.jpg"
    )


def test_load_image_decodes_png_from_storage(deduplication_set) -> None:
    source = np.zeros((8, 8, 3), dtype=np.uint8)
    source[0, 0] = (255, 0, 0)
    ok, buf = cv2.imencode(".png", source)
    assert ok

    encoding = Encoding.objects.create(
        deduplication_set=deduplication_set,
        reference_pk="img-load",
        filename=ContentFile(buf.tobytes(), name="img-load.png"),
    )

    decoded = load_image(encoding.filename)

    assert decoded.shape == (8, 8, 3)
    assert decoded[0, 0, 0] == 255

import cv2
import numpy as np
from django.db.models.fields.files import FieldFile
from numpy import ndarray


def encoding_image_key(group_reference_pk: str, deduplication_set_id: str, filename: str) -> str:
    """Return the deterministic storage key for an encoding image."""
    return f"images/{group_reference_pk}/{deduplication_set_id}/{filename}"


def load_image(file: FieldFile) -> ndarray:
    """Decode an encoding image from storage into a BGR OpenCV array."""
    with file.open("rb") as fh:
        buf = np.frombuffer(fh.read(), dtype=np.uint8)
    return cv2.imdecode(buf, cv2.IMREAD_COLOR)

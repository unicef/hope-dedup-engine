import cv2
import numpy as np
from django.core.files.storage import storages
from numpy import ndarray

from hope_dedup_engine.apps.api.exceptions import ImageDecodeError


def load_image(filename: str) -> ndarray:
    """Decode an encoding image from the shared HOPE blob storage into a BGR OpenCV array.

    Raises unchanged storage lookup errors (e.g. missing blob) plus ``ImageDecodeError``
    for unreadable data. Errors are not logged here; callers should log with their own
    business context (e.g. the encoding id) to avoid duplicate, context-poor log entries.
    """
    with storages["hope"].open(filename, "rb") as fh:
        buf = np.frombuffer(fh.read(), dtype=np.uint8)

    image = cv2.imdecode(buf, cv2.IMREAD_COLOR)
    if image is None:
        raise ImageDecodeError(f"Could not decode {filename} as an image: unsupported or corrupt data")

    return image

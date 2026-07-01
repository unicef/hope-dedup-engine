import cv2
import numpy as np
from django.core.files.storage import storages
from numpy import ndarray


def load_image(filename: str) -> ndarray:
    """Decode an encoding image from the shared HOPE blob storage into a BGR OpenCV array."""
    with storages["hope"].open(filename, "rb") as fh:
        buf = np.frombuffer(fh.read(), dtype=np.uint8)
    return cv2.imdecode(buf, cv2.IMREAD_COLOR)

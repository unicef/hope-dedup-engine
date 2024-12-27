from fnmatch import fnmatch
from typing import Final

from django.conf import settings

import cv2
import numpy as np
from storages.backends.azure_storage import AzureStorage

FILES_PATTERN: Final[tuple[str]] = ("*.png", "*.jpg", "*.jpeg")


class ImagesStorageManager:
    def __init__(self) -> None:
        self.storage: AzureStorage = AzureStorage(
            **settings.STORAGES.get("hope").get("OPTIONS")
        )

    def get_files(self, pattern: tuple = FILES_PATTERN) -> list[str]:
        _, images = self.storage.listdir("")
        return [f for f in images if any(fnmatch(f, p) for p in pattern)]

    def load_image(self, file: str) -> np.ndarray:
        with self.storage.open(file, "rb") as img_file:
            img_array = np.frombuffer(img_file.read(), dtype=np.uint8)
            img_bgr = cv2.imdecode(img_array, cv2.IMREAD_COLOR)
        return img_bgr

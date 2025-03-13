from django.conf import settings

import cv2
import numpy as np
from storages.backends.azure_storage import AzureStorage


class ImagesStorageManager:
    def __init__(self) -> None:
        self.storage: AzureStorage = AzureStorage(**settings.STORAGES.get("hope").get("OPTIONS"))

    def load_image(self, file: str) -> np.ndarray:
        with self.storage.open(file, "rb") as img_file:
            img_array = np.frombuffer(img_file.read(), dtype=np.uint8)
            img_bgr = cv2.imdecode(img_array, cv2.IMREAD_COLOR)
        return img_bgr

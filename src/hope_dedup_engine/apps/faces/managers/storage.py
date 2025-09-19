from pathlib import Path

from django.conf import settings

import cv2
import numpy as np
from azure.core.exceptions import ResourceNotFoundError
from storages.backends.azure_storage import AzureStorage


class ImagesStorageManager:
    def __init__(self) -> None:
        self.storage: AzureStorage = AzureStorage(**settings.STORAGES.get("hope").get("OPTIONS"))

    def load_image(self, file: str) -> np.ndarray:
        with self.storage.open(file, "rb") as img_file:
            img_array = np.frombuffer(img_file.read(), dtype=np.uint8)
            return cv2.imdecode(img_array, cv2.IMREAD_COLOR)


class LocalImagesStorageManager:
    def __init__(self) -> None:
        self.base_dir = Path(settings.LOCAL_IMAGE_DIR)

    def load_image(self, file: str) -> np.ndarray:
        image_path = self.base_dir / file
        if not image_path.is_file():
            raise ResourceNotFoundError(f"Image file not found: {image_path}")
        return cv2.imread(str(image_path), cv2.IMREAD_COLOR)


def get_storage_manager() -> ImagesStorageManager | LocalImagesStorageManager:
    backend = settings.IMAGE_STORAGE_BACKEND
    if backend == "local":
        if not settings.LOCAL_IMAGE_DIR:
            raise ValueError("LOCAL_IMAGE_DIR setting is required for 'local' storage backend.")
        if not Path(settings.LOCAL_IMAGE_DIR).is_dir():
            raise FileNotFoundError(f"Local image directory not found: {settings.LOCAL_IMAGE_DIR}")
        return LocalImagesStorageManager()
    if backend == "azure":
        return ImagesStorageManager()
    raise ValueError(f"Unsupported image storage backend: {backend}")

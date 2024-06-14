from django.conf import settings

from hope_dedup_engine.apps.core.storage import (
    CV2DNNStorage,
    HDEAzureStorage,
    HOPEAzureStorage,
)
from hope_dedup_engine.apps.faces.exceptions import StorageKeyError


class StorageManager:
    """
    A class to manage different types of storage systems used in the application.
    """

    def __init__(self) -> None:
        """
        Initialize the StorageManager.

        Raises:
            FileNotFoundError: If any of the required DNN model files do not exist in the storage.
        """
        self.storages: dict[str, HOPEAzureStorage | CV2DNNStorage | HDEAzureStorage] = {
            "images": HOPEAzureStorage(),
            "cv2dnn": CV2DNNStorage(settings.CV2DNN_PATH),
            "encoded": HDEAzureStorage(),
        }
        for file in (settings.PROTOTXT_FILE, settings.CAFFEMODEL_FILE):
            if not self.storages.get("cv2dnn").exists(file):
                raise FileNotFoundError(f"File {file} does not exist in storage.")

    def get_storage(
        self, key: str
    ) -> HOPEAzureStorage | CV2DNNStorage | HDEAzureStorage:
        """
        Get the storage object for the given key.

        Args:
            key (str): The key associated with the desired storage backend.

        Returns:
            HOPEAzureStorage | CV2DNNStorage | HDEAzureStorage: The storage object associated with the given key.

        Raises:
            StorageKeyError: If the given key does not exist in the storages dictionary.
        """
        if key not in self.storages:
            raise StorageKeyError(key)
        return self.storages[key]

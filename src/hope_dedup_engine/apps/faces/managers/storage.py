from django.conf import settings
from django.core.files.storage import FileSystemStorage

from storages.backends.azure_storage import AzureStorage

from hope_dedup_engine.apps.core.exceptions import StorageKeyError


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
        self.storages: dict[str, AzureStorage | FileSystemStorage] = {
            "cv2": FileSystemStorage(**settings.STORAGES.get("cv2").get("OPTIONS")),
            "images": AzureStorage(**settings.STORAGES.get("hope").get("OPTIONS")),
            "encoded": AzureStorage(**settings.STORAGES.get("encoded").get("OPTIONS")),
        }

        for file in (
            settings.DNN_FILES.get("prototxt").get("filename"),
            settings.DNN_FILES.get("caffemodel").get("filename"),
        ):
            if not self.storages.get("cv2").exists(file):
                raise FileNotFoundError(f"File {file} does not exist in storage.")

    def get_storage(self, key: str) -> AzureStorage | FileSystemStorage:
        """
        Get the storage object for the given key.

        Args:
            key (str): The key associated with the desired storage backend.

        Returns:
            AzureStorage | FileSystemStorage: The storage object associated with the given key.

        Raises:
            StorageKeyError: If the given key does not exist in the storages dictionary.
        """
        if key not in self.storages:
            raise StorageKeyError(key)
        return self.storages[key]

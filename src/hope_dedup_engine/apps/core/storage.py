from typing import Any

from django.conf import settings
from django.core.files.storage import FileSystemStorage

from storages.backends.azure_storage import AzureStorage


class UniqueStorageMixin:
    def get_available_name(self, name: str, max_length: int | None = None) -> str:
        if self.exists(name):
            self.delete(name)
        return name


class CV2DNNStorage(UniqueStorageMixin, FileSystemStorage):
    """
    Storage for files that needs cv2dnn DeepNeuralNetwork module of the OpenCV library.
    Here are placed:
    - prototxt file
    - caffemodel file
    """


class BaseAzureStorage(UniqueStorageMixin, AzureStorage):
    def __init__(self, azure_container: str, *args: Any, **kwargs: Any) -> None:
        self.account_name = settings.AZURE_ACCOUNT_NAME
        self.account_key = settings.AZURE_ACCOUNT_KEY
        self.custom_domain = settings.AZURE_CUSTOM_DOMAIN
        self.connection_string = settings.AZURE_CONNECTION_STRING
        self.azure_container = azure_container
        super().__init__(*args, **kwargs)


class ReadOnlyAzureStorage(BaseAzureStorage):
    def delete(self, name: str) -> None:
        raise RuntimeError("This storage cannot delete files")

    def open(self, name: str, mode: str = "rb") -> Any:
        if "w" in mode:
            raise RuntimeError("This storage cannot open files in write mode")
        return super().open(name, mode="rb")

    def save(self, name: str, content: Any, max_length: int | None = None) -> None:
        raise RuntimeError("This storage cannot save files")

    # def listdir(self, path: str = "") -> tuple[list[str], list[str]]:
    #     return [], []


class HDEAzureStorage(BaseAzureStorage):
    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(settings.AZURE_CONTAINER_HDE, *args, **kwargs)


class HOPEAzureStorage(ReadOnlyAzureStorage):
    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(settings.AZURE_CONTAINER_HOPE, *args, **kwargs)


class DNNAzureStorage(ReadOnlyAzureStorage):
    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(settings.AZURE_CONTAINER_DNN, *args, **kwargs)

"""
Service use 3 Azure containers:
- AZURE_CONTAINER_HDE: Writable container for encodings data.
- AZURE_CONTAINER_HOPE: Read-only container for images from HOPE.
- AZURE_CONTAINER_DNN: Read-only container for DNN files (deploy.prototxt and res10_300x300_ssd_iter_140000.caffemodel).

Depending on the value of constance.config.DNN_FILES_SOURCE, the service fetches DNN files from either GitHub or
AZURE_CONTAINER_DNN using a Celery task. At startup, if local DNN files are missing, the service triggers an automatic
download.

For manual interventions, access the admin panel at:
Home › Faces › DNN files.

Downloaded files are placed into the settings.CV2DNN_DIR folder. This folder must be accessible by both our backend and
Celery workers.

In the future, files within AZURE_CONTAINER_DNN may be automatically updated with new versions of our trained model via
a dedicated pipeline.
"""

from typing import Any

from django.conf import settings
from django.core.files.storage import FileSystemStorage

from azure.core.utils import parse_connection_string
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


class HDEAzureStorage(UniqueStorageMixin, AzureStorage):
    # connection_string: str
    # azure_container: str
    def __init__(self, *args: Any, **kwargs: Any) -> None:
        self.kwargs = kwargs
        super().__init__(*args, **kwargs)

    def get_default_settings(self):
        return {
            "account_key": self.kwargs.get("account_key"),
            "account_name": self.kwargs.get("account_name"),
            "api_version": self.kwargs.get("api_version", None),
            "azure_container": self.kwargs.get("azure_container"),
            "azure_ssl": self.kwargs.get("azure_ssl", True),
            "cache_control": self.kwargs.get("cache_control", ""),
            "connection_string": self.kwargs.get("connection_string"),
            "custom_domain": self.kwargs.get("custom_domain"),
            "default_content_type": "application/octet-stream",
            "endpoint_suffix": self.kwargs.get("endpoint_suffix", "core.windows.net"),
            "expiration_secs": self.kwargs.get("expiration_secs"),
            "location": self.kwargs.get("location", ""),
            "max_memory_size": self.kwargs.get("max_memory_size", 2 * 1024 * 1024),
            "object_parameters": self.kwargs.get("object_parameters", {}),
            "overwrite_files": self.kwargs.get("overwrite_files", False),
            "sas_token": self.kwargs.get("sas_token"),
            "timeout": self.kwargs.get("timeout", 20),
            "token_credential": self.kwargs.get("token_credential"),
            "upload_max_conn": self.kwargs.get("upload_max_conn", 2),
        }


class ReadOnlyAzureStorage(HDEAzureStorage):
    def delete(self, name: str) -> None:
        raise RuntimeError("This storage cannot delete files")

    def open(self, name: str, mode: str = "rb") -> Any:
        if "w" in mode:
            raise RuntimeError("This storage cannot open files in write mode")
        return super().open(name, mode="rb")

    def save(self, name: str, content: Any, max_length: int | None = None) -> None:
        raise RuntimeError("This storage cannot save files")


#
# class HDEAzureStorage(BaseAzureStorage):
#     def __init__(self, *args: Any, **kwargs: Any) -> None:
#         super().__init__(settings.AZURE_CONTAINER_HDE, *args, **kwargs)
#
#
# class HOPEAzureStorage(ReadOnlyAzureStorage):
#     def __init__(self, *args: Any, **kwargs: Any) -> None:
#         super().__init__(settings.AZURE_CONTAINER_HOPE, *args, **kwargs)
#
#
# class DNNAzureStorage(ReadOnlyAzureStorage):
#     def __init__(self, *args: Any, **kwargs: Any) -> None:
#         super().__init__(settings.AZURE_CONTAINER_DNN, *args, **kwargs)

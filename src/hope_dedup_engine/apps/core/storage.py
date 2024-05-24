from django.conf import settings
from django.core.files.storage import FileSystemStorage

from storages.backends.azure_storage import AzureStorage


class UniqueStorageMixin:
    def get_available_name(self, name: str, max_length: int | None = None) -> str:
        if self.exists(name):
            self.delete(name)
        return name


class CV2DNNStorage(UniqueStorageMixin, FileSystemStorage):
    pass


class HDEAzureStorage(UniqueStorageMixin, AzureStorage):
    def __init__(self, *args, **kwargs):
        self.account_name = settings.AZURE_ACCOUNT_NAME
        self.account_key = settings.AZURE_ACCOUNT_KEY
        self.custom_domain = settings.AZURE_CUSTOM_DOMAIN
        self.connection_string = settings.AZURE_CONNECTION_STRING
        super().__init__(*args, **kwargs)
        self.azure_container = settings.AZURE_CONTAINER_HDE


class HOPEAzureStorage(HDEAzureStorage):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.azure_container = settings.AZURE_CONTAINER_HOPE

    def delete(self, name):
        raise RuntimeError("This storage cannot delete files")

    def open(self, name, mode="rb"):
        if "w" in mode:
            raise RuntimeError("This storage cannot open files in write mode")
        return super().open(name, mode="rb")

    def save(self, name, content, max_length=None):
        raise RuntimeError("This storage cannot save files")

    def listdir(self, path=""):
        return []

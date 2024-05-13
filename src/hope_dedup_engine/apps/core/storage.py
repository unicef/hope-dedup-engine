from django.core.files.storage import FileSystemStorage

from storages.backends.azure_storage import AzureStorage


class DataSetStorage(FileSystemStorage):
    def get_available_name(self, name: str, max_length: int | None = None) -> str:
        if self.exists(name):
            self.delete(name)
        return name


class UniqueStorageMixin:
    def get_available_name(self, name: str, max_length: int | None = None) -> str:
        if self.exists(name):
            self.delete(name)
        return name


class HDEAzureStorage(UniqueStorageMixin, AzureStorage):
    pass

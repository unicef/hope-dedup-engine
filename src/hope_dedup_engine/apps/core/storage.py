from django.core.files.storage import FileSystemStorage

from storages.backends.azure_storage import AzureStorage


class UniqueStorageMixin:
    def get_available_name(self, name: str, max_length: int | None = None) -> str:
        if self.exists(name):
            self.delete(name)
        return name


class DataSetStorage(UniqueStorageMixin, FileSystemStorage):
    pass


class HDEAzureStorage(UniqueStorageMixin, AzureStorage):
    pass


class HOPEAzureStorage(HDEAzureStorage):
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

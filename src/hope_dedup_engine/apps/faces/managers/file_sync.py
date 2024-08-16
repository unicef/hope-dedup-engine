from pathlib import Path

from django.conf import settings
from django.core.files.storage import FileSystemStorage

import requests
from storages.backends.azure_storage import AzureStorage

from hope_dedup_engine.apps.core.exceptions import DownloaderKeyError


class FileDownloader:
    """
    Base class for downloading files from different sources.
    """

    def __init__(self) -> None:
        """
        Initializes the FileDownloader with a local storage backend.
        """
        self.local_storage = FileSystemStorage(
            **settings.STORAGES.get("cv2").get("OPTIONS")
        )

    def sync(
        self, filename: str, source: str, force: bool = False, *args, **kwargs
    ) -> bool:
        """
        Abstract method to synchronize a file from a source to the local storage.

        Args:
            filename (str): The name of the file to be saved.
            source (str): The source from where the file should be downloaded.
            force (bool): If True, the file will be re-downloaded even if it exists locally.

        Returns:
            bool: True if the file was downloaded successfully or already exists, False otherwise.

        Raises:
            NotImplementedError: If the method is not overridden by a subclass.
        """
        raise NotImplementedError("This method should be overridden by subclasses.")

    def _prepare_local_filepath(self, filename: str, force: bool) -> Path | None:
        """
        Prepares the local file path for the file to be downloaded.

        Args:
            filename (str): The name of the file.
            force (bool): If True, the file will be re-downloaded even if it exists locally.

        Returns:
            Path | None: The local file path if the file should be downloaded,
                         None if the file exists and `force` is False.
        """
        local_filepath = Path(self.local_storage.path(filename))
        if not force and local_filepath.exists():
            return None
        local_filepath.parent.mkdir(parents=True, exist_ok=True)
        return local_filepath


class GithubFileDownloader(FileDownloader):
    """
    Downloader class for downloading files from GitHub.

    Inherits from FileDownloader and implements the sync method to download files from a given GitHub URL.
    """

    def sync(
        self,
        filename: str,
        url: str,
        force: bool = False,
        timeout: int = 3 * 60,
        chunk_size: int = 128 * 1024,
    ) -> bool:
        """
        Downloads a file from the specified GitHub URL to local storage.

        Args:
            filename (str): The name of the file to be downloaded.
            url (str): The URL of the file on GitHub.
            force (bool): If True, the file will be re-downloaded even if it exists locally.
            timeout (int): The timeout for the download request in seconds. Default is 3 minutes.
            chunk_size (int): The size of chunks to download the file in bytes. Default is 128 KB.

        Returns:
            bool: True if the file was downloaded successfully or already exists, False otherwise.
        """
        local_filepath = self._prepare_local_filepath(filename, force)
        if local_filepath is None:
            return True

        with requests.get(url, stream=True, timeout=timeout) as r:
            r.raise_for_status()
            with local_filepath.open("wb") as f:
                for chunk in r.iter_content(chunk_size=chunk_size):
                    f.write(chunk)

        return True


class AzureFileDownloader(FileDownloader):
    """
    Downloader class for downloading files from Azure Blob Storage.

    Inherits from FileDownloader and implements the sync method to download files from a given Azure Blob Storage.
    """

    def __init__(self) -> None:
        """
        Initializes the AzureFileDownloader with a remote storage backend.
        """
        super().__init__()
        self.remote_storage = AzureStorage(
            **settings.STORAGES.get("dnn").get("OPTIONS")
        )

    def sync(
        self,
        filename: str,
        blob_name: str,
        force: bool = False,
        chunk_size: int = 128 * 1024,
    ) -> bool:
        """
        Downloads a file from the specified Azure Blob Storage to local storage.

        Args:
            filename (str): The name of the file to be downloaded.
            blob_name (str): The name of the blob in Azure Blob Storage.
            force (bool): If True, the file will be re-downloaded even if it exists locally.
            chunk_size (int): The size of chunks to download the file in bytes. Default is 128 KB.

        Returns:
            bool: True if the file was downloaded successfully or already exists, False otherwise.

        Raises:
            FileNotFoundError: If the file does not exist in the remote storage.
        """
        local_filepath = self._prepare_local_filepath(filename, force)
        if local_filepath is None:
            return True

        if not self.remote_storage.exists(blob_name):
            raise FileNotFoundError(
                f"File {blob_name} does not exist in remote storage"
            )

        with self.remote_storage.open(blob_name, "rb") as remote_file:
            with local_filepath.open("wb") as local_file:
                for chunk in remote_file.chunks(chunk_size=chunk_size):
                    local_file.write(chunk)

        return True


class FileSyncManager:
    def __init__(self, source: str) -> None:
        """
        Initialize the FileSyncManager with the specified source.

        Args:
            source (str): The source for downloading files.
        """
        self.downloader = self._create_downloader(source)

    def _create_downloader(self, source: str) -> FileDownloader:
        """
        Create an instance of the appropriate downloader based on the source.

        Args:
            source (str): The source for downloading files (e.g., 'github' or 'azure').

        Returns:
            FileDownloader: An instance of the appropriate downloader.

        Raises:
            DownloaderKeyError: If the source is not recognized.
        """
        downloader_classes = {
            "github": GithubFileDownloader,
            "azure": AzureFileDownloader,
        }
        try:
            return downloader_classes[source]()
        except KeyError:
            raise DownloaderKeyError(source)

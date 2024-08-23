from pathlib import Path
from typing import Callable

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
            **settings.STORAGES.get("default").get("OPTIONS")
        )

    def sync(
        self,
        filename: str,
        source: str,
        force: bool = False,
        on_progress: Callable[[str, int], None] = None,
        *args,
        **kwargs,
    ) -> bool:
        """
        Synchronize a file from the specified source to the local storage.

        Args:
            filename (str): The name of the file to be synchronized.
            source (str): The source from which the file should be downloaded.
            force (bool): If True, the file will be re-downloaded even if it already exists locally.
            on_progress (Callable[[str, int], None], optional): A callback function to report the download
                progress. The function should accept two arguments: the filename and the download progress
                as a percentage. Defaults to None.
            *args: Additional positional arguments for extended functionality in subclasses.
            **kwargs: Additional keyword arguments for extended functionality in subclasses.

        Returns:
            bool: True if the file was successfully synchronized or already exists locally,
                False otherwise.

        Raises:
            NotImplementedError: This method should be overridden by subclasses to provide
                                specific synchronization logic.
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

    def _report_progress(
        self,
        filename: str,
        downloaded: int,
        total: int,
        on_progress: Callable[[str, int], None] = None,
    ) -> None:
        """
        Reports the download progress of a file.

        Args:
            filename (str): The name of the file being downloaded.
            downloaded (int): The number of bytes that have been downloaded so far.
            total (int): The total size of the file in bytes.
            on_progress (Callable[[str, int], None], optional): A callback function that is called with the filename
                        and the download percentage. Defaults to None.

        Returns:
            None
        """
        if on_progress and total > 0:
            on_progress(filename, int((downloaded / total) * 100))


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
        on_progress: Callable[[str, int], None] = None,
        timeout: int = 3 * 60,
        chunk_size: int = 128 * 1024,
    ) -> bool:
        """
        Downloads a file from the specified URL and saves it to local storage.

        Args:
            filename (str): The name of the file to be downloaded.
            url (str): The URL of the file to download.
            force (bool): If True, the file will be re-downloaded even if it exists locally. Defaults to False.
            on_progress (Callable[[str, int], None], optional): A callback function that reports the download progress
                        as a percentage. Defaults to None.
            timeout (int): The timeout for the download request in seconds. Defaults to 3 minutes.
            chunk_size (int): The size of each chunk to download in bytes. Defaults to 128 KB.

        Returns:
            bool: True if the file was downloaded successfully or already exists, False otherwise.

        Raises:
            requests.exceptions.HTTPError: If the HTTP request returned an unsuccessful status code.
            FileNotFoundError: If the file at the specified URL is empty (size is 0 bytes).
        """
        local_filepath = self._prepare_local_filepath(filename, force)
        if local_filepath is None:
            return True

        with requests.get(url, stream=True, timeout=timeout) as r:
            r.raise_for_status()
            total, downloaded = int(r.headers.get("Content-Length", 1)), 0

            if total == 0:
                raise FileNotFoundError(
                    f"File {filename} at {url} is empty (size is 0 bytes)."
                )

            with local_filepath.open("wb") as f:
                for chunk in r.iter_content(chunk_size=chunk_size):
                    f.write(chunk)
                    downloaded += len(chunk)
                    self._report_progress(filename, downloaded, total, on_progress)

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
        on_progress: Callable[[str, int], None] = None,
        chunk_size: int = 128 * 1024,
    ) -> bool:
        """
        Downloads a file from Azure Blob Storage and saves it to local storage.

        Args:
            filename (str): The name of the file to be saved locally.
            blob_name (str): The name of the blob in Azure Blob Storage.
            force (bool): If True, the file will be re-downloaded even if it exists locally. Defaults to False.
            on_progress (Callable[[str, int], None], optional): A callback function that reports the download progress
                        as a percentage. Defaults to None.
            chunk_size (int): The size of each chunk to download in bytes. Defaults to 128 KB.

        Returns:
            bool: True if the file was downloaded successfully or already exists, False otherwise.

        Raises:
            FileNotFoundError: If the specified blob does not exist in Azure Blob Storage
                            or if the blob has a size of 0 bytes.
        """
        local_filepath = self._prepare_local_filepath(filename, force)
        if local_filepath is None:
            return True

        _, files = self.remote_storage.listdir("")
        if blob_name not in files:
            raise FileNotFoundError(
                f"File {blob_name} does not exist in remote storage"
            )

        blob_size, downloaded = self.remote_storage.size(blob_name) or 1, 0
        if blob_size == 0:
            raise FileNotFoundError(f"File {blob_name} is empty (size is 0 bytes).")

        with self.remote_storage.open(blob_name, "rb") as remote_file:
            with local_filepath.open("wb") as local_file:
                for chunk in remote_file.chunks(chunk_size=chunk_size):
                    local_file.write(chunk)
                    downloaded += len(chunk)
                    self._report_progress(filename, downloaded, blob_size, on_progress)

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

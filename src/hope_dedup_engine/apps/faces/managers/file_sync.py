from pathlib import Path

import requests

from hope_dedup_engine.apps.core.storage import DNNAzureStorage
from hope_dedup_engine.apps.faces.exceptions import DownloaderKeyError


class FileDownloader:
    def sync(self, source: str, local_path: Path, *args, **kwargs) -> bool:
        """
        Abstract method to synchronize a file from a source to a local path.

        Args:
            source (str): The source location of the file.
            local_path (Path): The local path where the file will be saved.

        Returns:
            bool: True if the file was successfully synchronized.

        Raises:
            NotImplementedError: If this method is not overridden by subclasses.
        """
        raise NotImplementedError("This method should be overridden by subclasses.")


class GithubFileDownloader(FileDownloader):
    def sync(
        self,
        url: str,
        local_path: Path,
        timeout: int = 3 * 60,
        chunk_size: int = 128 * 1024,
    ) -> bool:
        """
        Synchronize a file from a GitHub URL to a local path.

        Args:
            url (str): The URL of the file on GitHub.
            local_path (Path): The local path where the file will be saved.
            timeout (int, optional): The timeout for the HTTP request. Defaults to 3 minutes.
            chunk_size (int, optional): The chunk size for reading the file. Defaults to 128 KB.

        Returns:
            bool: True if the file was successfully synchronized.

        Raises:
            requests.RequestException: If there is an issue with the HTTP request.
        """
        local_path.parent.mkdir(parents=True, exist_ok=True)
        with requests.get(url, stream=True, timeout=timeout) as r:
            r.raise_for_status()
            with local_path.open("wb") as f:
                for chunk in r.iter_content(chunk_size=chunk_size):
                    f.write(chunk)
        return True


class AzureFileDownloader(FileDownloader):
    def sync(
        self, blob_name: str, local_path: Path, chunk_size: int = 128 * 1024
    ) -> bool:
        """
        Synchronize a file from an Azure blob to a local path.

        Args:
            blob_name (str): The name of the blob in Azure Blob Storage.
            local_path (Path): The local path where the file will be saved.
            chunk_size (int, optional): The chunk size for reading the file. Defaults to 128 KB.

        Returns:
            bool: True if the file was successfully synchronized.

        Raises:
            FileNotFoundError: If the blob does not exist in Azure Blob Storage.
        """
        local_path.parent.mkdir(parents=True, exist_ok=True)
        azure_storage = DNNAzureStorage()
        if not azure_storage.exists(blob_name):
            raise FileNotFoundError(
                "File %s does not exist in Azure Blob Storage", blob_name
            )

        with azure_storage.open(blob_name, "rb") as blob_file:
            with local_path.open("wb") as local_file:
                for chunk in blob_file.chunks(chunk_size=chunk_size):
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

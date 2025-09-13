from pathlib import Path
from typing import Callable, Final

from django.conf import settings
from django.core.files.storage import FileSystemStorage

import requests
from filelock import FileLock, Timeout
from storages.backends.azure_storage import AzureStorage

from hope_dedup_engine.apps.core.exceptions import DownloaderKeyError
import contextlib


class FileDownloader:
    """Base class for downloading files from different sources."""

    MESSAGES: Final[dict[str, str]] = {
        "not_implemented": "This method should be overridden by subclasses.",
        "file_exists": "File already exists locally.",
        "downloading": "Skipping download, another process is downloading the file.",
        "done": "Done.",
    }

    def __init__(self, local_base_location: Path) -> None:
        """Initialize the FileDownloader with a local storage backend."""
        self.local_storage = FileSystemStorage(
            **settings.STORAGES.get("default").get("OPTIONS"),
        )
        self.local_storage.base_location = local_base_location

    def sync(
        self,
        filename: str,
        file_source: str,
        force: bool = False,
        on_progress: Callable[[str, int], None] = None,
        **kwargs,
    ) -> str:
        """Synchronize a file with lock handling.

        This method ensures that a file is downloaded to the local storage with proper handling of concurrent access
        using file-based locks. If the file already exists locally or is currently being downloaded by another process,
        it will skip the download and return an appropriate message. The download process is thread- and process-safe.

        Args:
            filename (str): The name of the file to be synchronized.
            file_source (str): The source of the file (e.g., a URL or a blob name).
            force (bool): If True, forces the re-download of the file even if it already exists locally.
            on_progress (Callable[[str, int], None], optional): A callback function to track the download progress.
                The callback should accept the filename and the progress percentage as arguments. Defaults to None.
            **kwargs: Additional arguments passed to `_execute_download`.

        Returns:
            str: A message indicating the outcome of the synchronization.

        """
        local_filepath = Path(self.local_storage.path(filename))
        lock = FileLock(f"{local_filepath}.lock")

        if skip_message := self._should_skip_download(local_filepath, lock, force):
            return skip_message

        local_filepath.parent.mkdir(parents=True, exist_ok=True)

        try:
            with lock:
                return self._execute_download(local_filepath, file_source, on_progress=on_progress, **kwargs)
        except Timeout:
            return self.MESSAGES.get("downloading")
        finally:
            self._cleanup_lock(lock)

    def _should_skip_download(self, local_filepath: Path, lock: FileLock, force: bool) -> bool:
        """Determine if the download should be skipped."""
        if force:
            return None

        if local_filepath.exists():
            if Path(lock.lock_file).exists():
                try:
                    with lock.acquire(timeout=0):
                        pass
                except Timeout:
                    return self.MESSAGES.get("downloading")
            return self.MESSAGES.get("file_exists")

        return None

    def _execute_download(
        self,
        local_filepath: str,
        source: str,
        on_progress: Callable[[str, int], None] = None,
        *args,
        **kwargs,
    ) -> str:
        """Synchronize a file from the specified source to the local storage.

        Args:
            local_filepath (str): The local path where the file will be saved.
            source (str): The source of the file, e.g., a URL, blob name, or other identifier.
            force (bool): Whether to force the download even if the file already exists locally. Defaults to False.
            on_progress (Callable[[str, int], None], optional): A callback function for reporting download progress.
                The callback receives the filename and download progress as a percentage.
            *args: Additional positional arguments for extended functionality in subclasses.
            **kwargs: Additional keyword arguments for extended functionality in subclasses.

        Returns:
            str: A message indicating the status of the operation, typically "Done." if implemented.

        Raises:
            NotImplementedError: This method must be implemented in a subclass.

        """
        raise NotImplementedError(self.MESSAGES.get("not_implemented"))

    def _cleanup_lock(self, lock: FileLock) -> None:
        """Clean up the lock file if it exists."""
        lock_path = Path(lock.lock_file)
        if lock_path.exists():
            with contextlib.suppress(FileNotFoundError):
                lock_path.unlink()

    def _report_progress(
        self,
        filename: str,
        downloaded: int,
        total: int,
        on_progress: Callable[[str, int], None] = None,
    ) -> None:
        """Report the download progress of a file.

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


class AzureFileDownloader(FileDownloader):
    """Downloader class for downloading files from Azure Blob Storage.

    Inherits from FileDownloader and implements the sync method to download files from a given Azure Blob Storage.
    """

    MESSAGES: Final[dict[str, str]] = {
        **FileDownloader.MESSAGES,
        "does_not_exist": "File '%s' does not exist in remote storage.",
        "empty_file": "File '%s' is empty (size is 0 bytes).",
    }

    def __init__(self, local_base_location: Path) -> None:
        """Initialize the AzureFileDownloader with a remote storage backend."""
        super().__init__(local_base_location)
        self.remote_storage = AzureStorage(**settings.STORAGES.get("dnn").get("OPTIONS"))

    def _execute_download(
        self,
        local_filepath: str,
        blob_name: str,
        on_progress: Callable[[str, int], None] = None,
        chunk_size: int = 128 * 1024,
    ) -> str:
        """Download a file from Azure Blob Storage and save it to local storage.

        Args:
            local_filepath (str): The local path where the file will be saved.
            blob_name (str): The name of the blob to be downloaded from Azure Blob Storage.
            on_progress (Callable[[str, int], None], optional): A callback function for reporting download progress.
                The callback receives the filename and download progress as a percentage.
            chunk_size (int): The size of each chunk to download in bytes. Defaults to 128 KB.

        Returns:
            str: A message indicating the status of the download. Typically "Done." if successful.

        Raises:
            FileNotFoundError: If the specified blob does not exist or is empty (size 0 bytes).

        """
        _, files = self.remote_storage.listdir("")
        if blob_name not in files:
            raise FileNotFoundError(self.MESSAGES.get("does_not_exist") % blob_name)

        blob_size, downloaded = self.remote_storage.size(blob_name), 0
        if blob_size == 0:
            raise FileNotFoundError(self.MESSAGES.get("empty_file") % blob_name)

        with self.remote_storage.open(blob_name, "rb") as remote_file, local_filepath.open("wb") as local_file:
            for chunk in remote_file.chunks(chunk_size=chunk_size):
                local_file.write(chunk)
                downloaded += len(chunk)
                self._report_progress(local_filepath.name, downloaded, blob_size, on_progress)

        return self.MESSAGES.get("done")


class GithubFileDownloader(FileDownloader):
    """Downloader class for downloading files from GitHub.

    Inherits from FileDownloader and implements the sync method to download files from a given GitHub URL.
    """

    MESSAGES: Final[dict[str, str]] = {
        **FileDownloader.MESSAGES,
        "empty_file": "File '%s' at '%s' is empty (size is 0 bytes).",
    }

    def __init__(self, local_base_location: Path) -> None:
        super().__init__(local_base_location)

    def _execute_download(
        self,
        local_filepath: str,
        url: str,
        on_progress: Callable[[str, int], None] = None,
        timeout: int = 3 * 60,  # 3 minutes
        chunk_size: int = 128 * 1024,  # 128 KB
    ) -> str:
        """Download a file from a specified URL and save it to local storage.

        Args:
            local_filepath (str): The local path where the file will be saved.
            url (str): The URL of the file to be downloaded.
            on_progress (Callable[[str, int], None], optional): A callback function for reporting download progress.
                The callback receives the filename and download progress as a percentage. Defaults to None.
            timeout (int): The timeout for the download request in seconds. Defaults to 180 seconds (3 minutes).
            chunk_size (int): The size of each chunk to download in bytes. Defaults to 128 KB.

        Returns:
            str: A message indicating the status of the download. Typically "Done." if successful.

        Raises:
            requests.exceptions.HTTPError: If the HTTP request fails with a non-successful status code.
            FileNotFoundError: If the file is empty (size 0 bytes) or the URL is inaccessible.

        """
        with requests.get(url, stream=True, timeout=timeout) as r:
            r.raise_for_status()
            total_str = r.headers.get("Content-Length")
            total, downloaded = (int(total_str), 0) if total_str is not None else (0, 0)

            if total == 0 and total_str is not None:
                raise FileNotFoundError(self.MESSAGES.get("empty_file") % (local_filepath.name, url))

            with local_filepath.open("wb") as f:
                for chunk in r.iter_content(chunk_size=chunk_size):
                    f.write(chunk)
                    downloaded += len(chunk)
                    self._report_progress(local_filepath.name, downloaded, total, on_progress)
            if on_progress:
                self._report_progress(local_filepath.name, total or downloaded, total or downloaded, on_progress)
        return self.MESSAGES.get("done")


class FileSyncManager:
    def __init__(self, *, source: str, local_base_location: Path | None = None) -> None:
        """Initialize the FileSyncManager with the specified source.

        Args:
            source (str): The source for downloading files.
            local_base_location (Path): The base location for storing files locally.

        """
        if local_base_location is None:
            local_base_location = Path(settings.DEFAULT_ROOT)
        self.local_base_location = local_base_location
        self.downloader = self._create_downloader(source)

    def _create_downloader(self, source: str) -> FileDownloader:
        """Create an instance of the appropriate downloader based on the source.

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
            return downloader_classes[source](self.local_base_location)
        except KeyError:
            raise DownloaderKeyError(source)

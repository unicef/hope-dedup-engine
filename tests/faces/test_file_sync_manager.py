import pytest

from hope_dedup_engine.apps.faces.exceptions import DownloaderKeyError
from hope_dedup_engine.apps.faces.managers import FileSyncManager
from hope_dedup_engine.apps.faces.managers.file_sync import (
    AzureFileDownloader,
    GithubFileDownloader,
)


@pytest.mark.parametrize(
    "downloader_key, expected_downloader",
    [
        ("github", GithubFileDownloader),
        ("azure", AzureFileDownloader),
    ],
)
def test_create_downloader(downloader_key, expected_downloader):
    file_sync_manager = FileSyncManager(downloader_key)
    assert isinstance(file_sync_manager.downloader, expected_downloader)


def test_create_downloader_failure():
    with pytest.raises(DownloaderKeyError):
        FileSyncManager("unknown")

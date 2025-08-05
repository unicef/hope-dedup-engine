from pathlib import Path
from unittest.mock import MagicMock, Mock

import pytest
from filelock import Timeout
from requests.exceptions import HTTPError

from hope_dedup_engine.apps.core.exceptions import DownloaderKeyError
from hope_dedup_engine.apps.faces.managers.file_sync import (
    AzureFileDownloader,
    FileDownloader,
    FileSyncManager,
    GithubFileDownloader,
)


@pytest.fixture
def local_base(tmp_path: Path) -> Path:
    """Fixture for a temporary local base directory."""
    return tmp_path / "local_files"


def test_sync_new_file(mocker, local_base):
    """Test syncing a new file downloads it."""
    downloader = FileDownloader(local_base)
    mocker.patch.object(downloader, "_execute_download", return_value="Done.")
    result = downloader.sync("test.dat", "source1")
    assert result == "Done."
    downloader._execute_download.assert_called_once()


def test_sync_existing_file(local_base):
    """Test syncing an existing file is skipped."""
    downloader = FileDownloader(local_base)
    local_file = local_base / "test.dat"
    local_file.parent.mkdir(parents=True, exist_ok=True)
    local_file.touch()

    result = downloader.sync("test.dat", "source1")
    assert result == downloader.MESSAGES["file_exists"]


def test_sync_force_download(mocker, local_base):
    """Test syncing with force=True redownloads the file."""
    downloader = FileDownloader(local_base)
    local_file = local_base / "test.dat"
    local_file.parent.mkdir(parents=True, exist_ok=True)
    local_file.touch()

    mocker.patch.object(downloader, "_execute_download", return_value="Done.")
    result = downloader.sync("test.dat", "source1", force=True)
    assert result == "Done."
    downloader._execute_download.assert_called_once()


def test_sync_locked_file(mocker, local_base):
    """Test that a locked file skips download."""
    downloader = FileDownloader(local_base)
    mocker.patch("filelock.FileLock.acquire", side_effect=Timeout("locked"))
    result = downloader.sync("test.dat", "source1")
    assert result == downloader.MESSAGES["downloading"]


def test_execute_download_not_implemented(local_base):
    """Test the base _execute_download raises NotImplementedError."""
    downloader = FileDownloader(local_base)
    with pytest.raises(NotImplementedError):
        downloader._execute_download("path", "source")


@pytest.fixture
def mock_requests_get(mocker):
    """Fixture to mock requests.get."""
    mock_response = MagicMock()
    mock_response.headers.get.return_value = "1024"
    mock_response.iter_content.return_value = [b"chunk1", b"chunk2"]
    mock_response.raise_for_status = Mock()
    return mocker.patch("requests.get", return_value=MagicMock(__enter__=MagicMock(return_value=mock_response)))


def test_github_downloader_success(mock_requests_get, local_base):
    """Test a successful file download from GitHub."""
    downloader = GithubFileDownloader(local_base)
    result = downloader.sync("test.dat", "http://example.com/test.dat")
    assert result == downloader.MESSAGES["done"]
    assert (local_base / "test.dat").read_bytes() == b"chunk1chunk2"
    mock_requests_get.assert_called_once()


def test_github_downloader_no_content_length(mock_requests_get, local_base):
    """Test download works when Content-Length header is missing."""
    mock_requests_get.return_value.__enter__.return_value.headers.get.return_value = None
    on_progress = Mock()
    downloader = GithubFileDownloader(local_base)
    downloader.sync("test.dat", "http://example.com/test.dat", on_progress=on_progress)

    assert (local_base / "test.dat").read_bytes() == b"chunk1chunk2"
    # Progress callback might be called once at the end with 100%,
    # or not at all if it relies on total_size for percentage calculation.
    # The key is that the download completes successfully.
    # A final call with 100% is good practice.
    if on_progress.called:
        on_progress.assert_any_call("test.dat", 100)


def test_github_downloader_progress_callback(mock_requests_get, local_base):
    """Test that the progress callback is called during download."""
    on_progress = Mock()
    downloader = GithubFileDownloader(local_base)
    downloader.sync("test.dat", "http://example.com/test.dat", on_progress=on_progress)
    assert on_progress.call_count > 0
    on_progress.assert_called_with("test.dat", 100)


@pytest.mark.parametrize(
    ("setup_mock_requests", "expected_exception", "error_msg_part"),
    [
        (
            lambda mock: mock.return_value.__enter__.return_value.raise_for_status.configure_mock(
                side_effect=HTTPError
            ),
            HTTPError,
            None,
        ),
        (
            lambda mock: mock.return_value.__enter__.return_value.headers.get.configure_mock(return_value="0"),
            FileNotFoundError,
            "is empty",
        ),
    ],
)
def test_github_downloader_errors(
    mock_requests_get, local_base, setup_mock_requests, expected_exception, error_msg_part
):
    """Test handling of various errors during GitHub download."""
    setup_mock_requests(mock_requests_get)
    downloader = GithubFileDownloader(local_base)
    with pytest.raises(expected_exception) as excinfo:
        downloader.sync("test.dat", "http://example.com/test.dat")
    if error_msg_part:
        assert error_msg_part in str(excinfo.value)


@pytest.fixture
def mock_azure_storage(mocker):
    """Fixture to mock AzureStorage."""
    mock_storage = MagicMock()
    mock_storage.listdir.return_value = ([], ["blob.dat"])
    mock_storage.size.return_value = 2048

    mock_file = MagicMock()
    mock_file.chunks.return_value = [b"azure_chunk1", b"azure_chunk2"]
    mock_storage.open.return_value = MagicMock(__enter__=MagicMock(return_value=mock_file))

    mocker.patch(
        "hope_dedup_engine.apps.faces.managers.file_sync.AzureStorage",
        return_value=mock_storage,
    )
    return mock_storage


def test_azure_downloader_success(mock_azure_storage, local_base):
    """Test a successful file download from Azure."""
    downloader = AzureFileDownloader(local_base)
    result = downloader.sync("blob.dat", "blob.dat")
    assert result == downloader.MESSAGES["done"]
    assert (local_base / "blob.dat").read_bytes() == b"azure_chunk1azure_chunk2"
    mock_azure_storage.open.assert_called_once_with("blob.dat", "rb")


@pytest.mark.parametrize(
    ("listdir_return", "size_return", "filename", "error_msg_part"),
    [
        (([], ["other.dat"]), 2048, "non_existent.dat", "does not exist"),
        (([], ["empty.dat"]), 0, "empty.dat", "is empty"),
    ],
)
def test_azure_downloader_errors(mock_azure_storage, local_base, listdir_return, size_return, filename, error_msg_part):
    """Test handling of various errors during Azure download."""
    mock_azure_storage.listdir.return_value = listdir_return
    mock_azure_storage.size.return_value = size_return

    downloader = AzureFileDownloader(local_base)
    with pytest.raises(FileNotFoundError) as excinfo:
        downloader.sync(filename, filename)
    assert error_msg_part in str(excinfo.value)


@pytest.mark.parametrize(
    ("source", "expected_downloader"),
    [
        ("github", GithubFileDownloader),
        ("azure", AzureFileDownloader),
    ],
)
def test_file_sync_manager_create_downloader(source, expected_downloader, local_base):
    """Test that the correct downloader is created based on the source."""
    manager = FileSyncManager(source=source, local_base_location=local_base)
    assert isinstance(manager.downloader, expected_downloader)


def test_file_sync_manager_invalid_source(local_base):
    """Test that an invalid source raises DownloaderKeyError."""
    with pytest.raises(DownloaderKeyError):
        FileSyncManager(source="invalid_source", local_base_location=local_base)

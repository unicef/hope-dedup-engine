from unittest.mock import mock_open, patch

import pytest
from faces_const import DNN_FILE
from requests.exceptions import RequestException

from hope_dedup_engine.apps.faces.managers import FileSyncManager
from hope_dedup_engine.apps.faces.managers.file_sync import (
    AzureFileDownloader,
    GithubFileDownloader,
)


def test_github_sync_success(github_dnn_file_downloader, mock_requests_get):
    url = DNN_FILE["url"]
    with patch("pathlib.Path.open", mock_open()) as mocked_file:
        result = github_dnn_file_downloader.sync(DNN_FILE["name"], url)

        assert result is True
        mock_requests_get.assert_called_once_with(
            url, stream=True, timeout=DNN_FILE["timeout"]
        )
        mocked_file.assert_called_once_with("wb")
        assert mocked_file().write.call_count == DNN_FILE["chunks"]


def test_github_sync_raises_exception(github_dnn_file_downloader, mock_requests_get):
    mock_requests_get.side_effect = RequestException("Failed to connect")

    with pytest.raises(RequestException):
        github_dnn_file_downloader.sync(DNN_FILE["name"], DNN_FILE["url"])
    mock_requests_get.assert_called_once_with(
        DNN_FILE["url"], stream=True, timeout=DNN_FILE["timeout"]
    )


def test_azure_sync_success(azure_dnn_file_downloader):
    with (
        patch.object(
            azure_dnn_file_downloader.remote_storage, "exists", return_value=True
        ),
        patch("pathlib.Path.open", mock_open()) as mocked_file,
    ):
        result = azure_dnn_file_downloader.sync(DNN_FILE["name"], DNN_FILE["name"])

        assert result is True
        azure_dnn_file_downloader.remote_storage.exists.assert_called_once_with(
            DNN_FILE["name"]
        )
        azure_dnn_file_downloader.remote_storage.open.assert_called_once_with(
            DNN_FILE["name"], "rb"
        )
        mocked_file.assert_called_once_with("wb")


def test_azure_sync_raises_filenotfounderror(azure_dnn_file_downloader):
    azure_dnn_file_downloader.remote_storage.exists.return_value = False

    with pytest.raises(FileNotFoundError):
        azure_dnn_file_downloader.sync(DNN_FILE["name"], DNN_FILE["name"])

    azure_dnn_file_downloader.remote_storage.exists.assert_called_once_with(
        DNN_FILE["name"]
    )
    azure_dnn_file_downloader.remote_storage.open.assert_not_called()


def test_filesyncmanager_creates_correct_downloader():
    github_manager = FileSyncManager("github")
    assert isinstance(github_manager.downloader, GithubFileDownloader)

    azure_manager = FileSyncManager("azure")
    assert isinstance(azure_manager.downloader, AzureFileDownloader)


def test_file_downloader_prepare_local_filepath_exists(
    github_dnn_file_downloader, mocker
):
    mock_path = mocker.patch("pathlib.Path.exists", return_value=True)

    result = github_dnn_file_downloader._prepare_local_filepath(
        DNN_FILE["name"], force=False
    )
    assert result is None
    mock_path.assert_called_once()


def test_file_downloader_prepare_local_filepath_force(
    github_dnn_file_downloader, mocker
):
    mocker.patch("pathlib.Path.exists", return_value=True)
    mock_path_mkdir = mocker.patch("pathlib.Path.mkdir")

    result = github_dnn_file_downloader._prepare_local_filepath(
        DNN_FILE["name"], force=True
    )
    assert result is not None
    mock_path_mkdir.assert_called_once_with(parents=True, exist_ok=True)

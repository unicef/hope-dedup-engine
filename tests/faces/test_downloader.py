from unittest.mock import mock_open, patch

import pytest
from faces_const import DNN_FILE
from requests.exceptions import RequestException


def test_github_sync_success(github_dnn_file_downloader, mock_requests_get, local_path):
    with patch("pathlib.Path.open", mock_open()) as mocked_file:
        result = github_dnn_file_downloader.sync(DNN_FILE["url"], local_path)

        assert result is True
        mock_requests_get.assert_called_once_with(
            DNN_FILE["url"], stream=True, timeout=DNN_FILE["timeout"]
        )
        mocked_file.assert_called_once_with("wb")
        assert mocked_file().write.call_count == DNN_FILE["chunks"]


def test_github_sync_raises_exception(
    github_dnn_file_downloader, mock_requests_get, local_path
):
    mock_requests_get.side_effect = RequestException("Failed to connect")
    with pytest.raises(RequestException):
        github_dnn_file_downloader.sync(DNN_FILE["url"], local_path)
    assert not local_path.exists()


def test_azure_dnn_sync_success(azure_dnn_file_downloader, local_path):
    with patch("pathlib.Path.open", mock_open()) as mocked_file:
        result = azure_dnn_file_downloader.sync(DNN_FILE.get("name"), local_path)

        assert result is True
        azure_dnn_file_downloader.storage.exists.assert_called_once_with(
            DNN_FILE.get("name")
        )
        azure_dnn_file_downloader.storage.open.assert_called_once_with(
            DNN_FILE.get("name"), "rb"
        )
        mocked_file.assert_called_once_with("wb")


def test_azure_dnn_sync_raises_exception(azure_dnn_file_downloader, local_path):
    azure_dnn_file_downloader.storage.exists.return_value = False
    with pytest.raises(FileNotFoundError):
        azure_dnn_file_downloader.sync(DNN_FILE.get("name"), local_path)
    assert not local_path.exists()

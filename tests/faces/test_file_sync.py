from unittest.mock import patch

from django.urls import reverse

import pytest

from hope_dedup_engine.apps.core.exceptions import DownloaderKeyError
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


@pytest.mark.parametrize(
    "active_queues, expected_call_count, multiple_workers, delay_called",
    [
        (None, 0, False, False),
        ({"worker1": "queue"}, 1, False, True),
        ({"worker1": "queue", "worker2": "queue"}, 2, True, False),
    ],
)
def test_sync_dnn_files(
    client, active_queues, expected_call_count, multiple_workers, delay_called
):
    with (
        patch(
            "hope_dedup_engine.apps.faces.admin.celery_app.control.inspect"
        ) as mock_inspect,
        patch(
            "hope_dedup_engine.apps.faces.admin.DummyModelAdmin.message_user"
        ) as mock_message_user,
        patch("hope_dedup_engine.apps.faces.admin.sync_dnn_files.s") as mock_s,
        patch("hope_dedup_engine.apps.faces.admin.group") as mock_group,
        patch("hope_dedup_engine.apps.faces.admin.sync_dnn_files.delay") as mock_delay,
    ):

        mock_inspect.return_value.active_queues.return_value = active_queues

        url = reverse("admin:faces_dummymodel_sync_dnn_files")
        response = client.get(url, follow=True)

        assert response.status_code == 200

        if multiple_workers:
            list(mock_group.call_args[0][0])
            mock_group.assert_called_once()
            assert mock_s.call_count == expected_call_count
            mock_group.return_value.apply_async.assert_called_once()

        if delay_called:
            mock_delay.assert_called_once_with(force=True)

        mock_inspect.return_value.active_queues.assert_called_once()
        mock_message_user.assert_called_once()

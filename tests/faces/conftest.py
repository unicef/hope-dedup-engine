from unittest.mock import MagicMock, patch
import pytest
from django.contrib.auth import get_user_model
from django.core.files.storage import FileSystemStorage
from django.test import Client
from docker import from_env
from freezegun import freeze_time
from pytest_mock import MockerFixture
from storages.backends.azure_storage import AzureStorage

from hope_dedup_engine.apps.faces.managers import ImagesStorageManager


@pytest.fixture
def mock_storage_manager(mocker: MockerFixture) -> ImagesStorageManager:
    mocker.patch.object(FileSystemStorage, "exists", return_value=True)
    mocker.patch.object(AzureStorage, "exists", return_value=True)
    return ImagesStorageManager()


@pytest.fixture
def mock_encoded_azure_storage(mocker: MockerFixture):
    return MagicMock(spec=AzureStorage)


@pytest.fixture
def mock_hope_azure_storage(mocker: MockerFixture):
    return MagicMock(spec=AzureStorage)


@pytest.fixture(scope="session")
def docker_client():
    client = from_env()
    yield client
    client.close()


@pytest.fixture
def mock_redis_client():
    with (
        patch("redis.Redis.set") as mock_set,
        patch("redis.Redis.delete") as mock_delete,
    ):
        yield mock_set, mock_delete


@pytest.fixture
def time_control():
    with freeze_time("2024-01-01") as frozen_time:
        yield frozen_time


@pytest.fixture
def mock_file_sync_manager():
    with patch("hope_dedup_engine.apps.faces.celery_tasks.FileSyncManager") as mock_file_sync_manager_class:
        mock_manager_instance = mock_file_sync_manager_class.return_value
        mock_downloader = MagicMock()
        mock_manager_instance.downloader = mock_downloader
        yield mock_manager_instance


@pytest.fixture
def admin_user(db):
    user_model = get_user_model()
    return user_model.objects.create_superuser(username="admin", password="admin", email="admin@example.com")


@pytest.fixture
def client(admin_user):
    client = Client()
    client.force_login(admin_user)
    return client

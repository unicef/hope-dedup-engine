from django.core.files.storage import FileSystemStorage

import pytest
from storages.backends.azure_storage import AzureStorage

from hope_dedup_engine.apps.core.exceptions import StorageKeyError
from hope_dedup_engine.apps.faces.managers import StorageManager


def test_initialization(mock_storage_manager):
    assert isinstance(
        mock_storage_manager.storages["cv2"],
        FileSystemStorage,
    )
    assert isinstance(
        mock_storage_manager.storages["images"],
        AzureStorage,
    )
    assert isinstance(
        mock_storage_manager.storages["encoded"],
        FileSystemStorage,
    )


def test_missing_file():
    with pytest.raises(FileNotFoundError):
        StorageManager()


def test_invalid_key(mock_storage_manager):
    with pytest.raises(StorageKeyError):
        mock_storage_manager.get_storage("invalid_key")


@pytest.mark.parametrize(
    "test_input, expected_method",
    [
        ("images", "exists"),
        ("cv2", "exists"),
        ("encoded", "exists"),
    ],
)
def test_valid_key(mock_storage_manager, test_input, expected_method):
    storage_object = mock_storage_manager.get_storage(test_input)
    assert hasattr(storage_object, expected_method)

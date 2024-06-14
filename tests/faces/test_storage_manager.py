import pytest

from hope_dedup_engine.apps.core.storage import CV2DNNStorage, HDEAzureStorage, HOPEAzureStorage
from hope_dedup_engine.apps.faces.exceptions import StorageKeyError
from hope_dedup_engine.apps.faces.managers.storage import StorageManager


def test_initialization(mock_storage_manager):
    assert isinstance(mock_storage_manager.storages["images"], HOPEAzureStorage)
    assert isinstance(mock_storage_manager.storages["cv2dnn"], CV2DNNStorage)
    assert isinstance(mock_storage_manager.storages["encoded"], HDEAzureStorage)


def test_missing_file():
    with pytest.raises(FileNotFoundError):
        StorageManager()


def test_invalid_key(mock_storage_manager):
    with pytest.raises(StorageKeyError):
        mock_storage_manager.get_storage("invalid_key")


@pytest.mark.parametrize(
    "test_input, expected_output",
    [
        ("images", HOPEAzureStorage),
        ("cv2dnn", CV2DNNStorage),
        ("encoded", HDEAzureStorage),
    ],
)
def test_valid_key(mock_storage_manager, test_input, expected_output):
    storage_object = mock_storage_manager.get_storage(test_input)
    assert isinstance(storage_object, expected_output)

from pathlib import Path

import cv2
import numpy as np
import pytest
from azure.core.exceptions import ResourceNotFoundError

from hope_dedup_engine.apps.faces.managers.storage import (
    ImagesStorageManager,
    LocalImagesStorageManager,
    get_storage_manager,
)


@pytest.mark.parametrize(
    ("backend", "local_dir", "dir_exists", "expected_result", "expected_exception"),
    [
        ("local", "/tmp/images", True, LocalImagesStorageManager, None),
        ("azure", None, False, ImagesStorageManager, None),
        ("local", None, False, None, ValueError),
        ("local", "/nonexistent_dir", False, None, FileNotFoundError),
        ("invalid", None, False, None, ValueError),
    ],
)
def test_get_storage_manager(settings, tmp_path, backend, local_dir, dir_exists, expected_result, expected_exception):
    """Test the get_storage_manager factory function under various conditions."""
    settings.IMAGE_STORAGE_BACKEND = backend
    if local_dir:
        if dir_exists:
            test_dir = tmp_path / "images"
            test_dir.mkdir()
            settings.LOCAL_IMAGE_DIR = str(test_dir)
        else:
            settings.LOCAL_IMAGE_DIR = local_dir
    else:
        settings.LOCAL_IMAGE_DIR = None

    if expected_exception:
        with pytest.raises(expected_exception):
            get_storage_manager()
    else:
        manager = get_storage_manager()
        assert isinstance(manager, expected_result)


def test_local_images_storage_manager(tmp_path: Path):
    """Test successfully loading an image with LocalImagesStorageManager."""
    image_dir = tmp_path / "images"
    image_dir.mkdir()
    image_path = image_dir / "test.jpg"

    dummy_image = np.zeros((100, 100, 3), dtype=np.uint8)
    cv2.imwrite(str(image_path), dummy_image)

    manager = LocalImagesStorageManager()
    manager.base_dir = image_dir

    loaded_image = manager.load_image("test.jpg")
    assert isinstance(loaded_image, np.ndarray)
    assert loaded_image.shape == (100, 100, 3)


def test_local_images_storage_manager_load_not_found(tmp_path: Path):
    """Test that ResourceNotFoundError is raised for a missing file."""
    manager = LocalImagesStorageManager()
    manager.base_dir = tmp_path
    with pytest.raises(ResourceNotFoundError):
        manager.load_image("nonexistent.jpg")


def test_images_storage_manager_load_image(mocker):
    """Test that ImagesStorageManager correctly calls the azure storage backend."""
    mock_azure_storage_class = mocker.patch("hope_dedup_engine.apps.faces.managers.storage.AzureStorage")
    mock_azure_storage_instance = mock_azure_storage_class.return_value

    mock_file = mocker.MagicMock()
    mock_file.read.return_value = b"some_image_bytes"
    mock_azure_storage_instance.open.return_value.__enter__.return_value = mock_file
    mocker.patch("cv2.imdecode", return_value=np.zeros((10, 10, 3)))

    manager = ImagesStorageManager()
    manager.load_image("test.jpg")

    mock_azure_storage_instance.open.assert_called_once_with("test.jpg", "rb")

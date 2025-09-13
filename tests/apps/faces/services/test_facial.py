from unittest.mock import Mock

import pytest
from azure.core.exceptions import ResourceNotFoundError

from hope_dedup_engine.apps.api.models import Image
from hope_dedup_engine.apps.faces.services.facial import (
    default_progress,
    encode_faces,
)


def test_default_progress():
    """Test that the default_progress function returns True."""
    assert default_progress("arg1", "arg2") is True


@pytest.fixture
def mock_deepface(mocker):
    """Fixture to mock the entire DeepFace module."""
    return mocker.patch("hope_dedup_engine.apps.faces.services.facial.DeepFace")


@pytest.fixture
def mock_storage(mocker):
    """Fixture to mock the ImagesStorageManager."""
    storage_mock = mocker.patch("hope_dedup_engine.apps.faces.services.facial.ImagesStorageManager").return_value
    storage_mock.load_image.return_value = "image_data"
    return storage_mock


@pytest.mark.django_db
def test_encode_faces_success(mock_deepface, mock_storage):
    """Test successful encoding of faces for a list of files."""
    files = ["file1.jpg", "file2.jpg"]
    mock_deepface.represent.side_effect = [[{"embedding": [1.0]}], [{"embedding": [2.0]}]]

    encoded, added, existing = encode_faces(files)

    assert added == 2
    assert existing == 1000  # Based on hardcoded value in function
    assert encoded == {"file1.jpg": [1.0], "file2.jpg": [2.0]}
    assert mock_deepface.represent.call_count == 2


@pytest.mark.django_db
def test_encode_faces_with_pre_encodings(mock_deepface, mock_storage):
    """Test that files with pre-existing encodings are not re-encoded."""
    files = ["file1.jpg", "file2.jpg"]
    pre_encodings = {"file1.jpg": [1.0]}
    mock_deepface.represent.return_value = [{"embedding": [2.0]}]

    encoded, added, existing = encode_faces(files, pre_encodings=pre_encodings)

    assert added == 1
    assert existing == 1001
    assert encoded == {"file1.jpg": [1.0], "file2.jpg": [2.0]}
    mock_deepface.represent.assert_called_once_with("image_data")


@pytest.mark.django_db
def test_encode_faces_progress_callback(mock_deepface, mock_storage):
    """Test that the progress callback is called for each file."""
    files = ["file1.jpg", "file2.jpg"]
    mock_deepface.represent.return_value = [{"embedding": [1.0]}]
    progress_mock = Mock()

    encode_faces(files, progress=progress_mock)
    assert progress_mock.call_count == len(files)


@pytest.mark.django_db
@pytest.mark.parametrize(
    ("represent_kwargs", "expected_status"),
    [
        (
            {"return_value": [{"embedding": [1.0]}, {"embedding": [2.0]}]},
            Image.StatusCode.MULTIPLE_FACES_DETECTED,
        ),
        ({"side_effect": TypeError("generic error")}, Image.StatusCode.GENERIC_ERROR),
        ({"side_effect": ValueError("no face detected")}, Image.StatusCode.NO_FACE_DETECTED),
    ],
)
def test_encode_faces_deepface_outcomes(mock_deepface, mock_storage, represent_kwargs, expected_status):
    """Test handling of various outcomes from DeepFace.represent."""
    files = ["file1.jpg"]
    mock_deepface.represent.configure_mock(**represent_kwargs)

    encoded, _, _ = encode_faces(files)
    assert encoded["file1.jpg"] == expected_status.name


@pytest.mark.django_db
def test_encode_faces_file_not_found(mock_deepface, mock_storage):
    """Test handling of ResourceNotFoundError from storage."""
    files = ["file1.jpg"]
    mock_storage.load_image.side_effect = ResourceNotFoundError("File not found")

    encoded, _, _ = encode_faces(files)
    assert encoded["file1.jpg"] == Image.StatusCode.NO_FILE_FOUND.name
    mock_deepface.represent.assert_not_called()

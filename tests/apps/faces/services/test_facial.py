import copy
from unittest.mock import Mock

import pytest
from azure.core.exceptions import ResourceNotFoundError

from hope_dedup_engine.apps.api.models import Image
from hope_dedup_engine.apps.faces.services.facial import (
    dedupe_images,
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


@pytest.fixture
def sample_data():
    """Provide sample data for deduplication tests."""
    return {
        "files0": ["file1.jpg"],
        "files1": ["file2.jpg"],
        "encodings": {"file1.jpg": [1.0], "file2.jpg": [1.1]},
        "ignored_pairs": set(),
        "dedupe_threshold": 0.9,
    }


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
    assert encoded["file1.jpg"] == expected_status.value


@pytest.mark.django_db
def test_encode_faces_file_not_found(mock_deepface, mock_storage):
    """Test handling of ResourceNotFoundError from storage."""
    files = ["file1.jpg"]
    mock_storage.load_image.side_effect = ResourceNotFoundError("File not found")

    encoded, _, _ = encode_faces(files)
    assert encoded["file1.jpg"] == Image.StatusCode.NO_FILE_FOUND.value
    mock_deepface.represent.assert_not_called()


@pytest.mark.django_db
@pytest.mark.parametrize(
    ("verify_return", "expected_result"),
    [
        ({"distance": 0.05}, [("file1.jpg", "file2.jpg", 0.95, Image.StatusCode.DEDUPLICATE_SUCCESS.value)]),
        ({"distance": 0.2}, []),
    ],
)
def test_dedupe_images_similarity_threshold(mock_deepface, sample_data, verify_return, expected_result):
    """Test dedupe_images with different similarity scores."""
    mock_deepface.verify.return_value = verify_return
    results = dedupe_images(**sample_data)
    assert results == expected_result
    mock_deepface.verify.assert_called_once_with(
        sample_data["encodings"]["file1.jpg"], sample_data["encodings"]["file2.jpg"]
    )


@pytest.mark.django_db
def test_dedupe_images_with_ignored_pair(mock_deepface, sample_data):
    """Test that ignored pairs are not compared."""
    test_data = copy.deepcopy(sample_data)
    test_data["ignored_pairs"] = {("file1.jpg", "file2.jpg")}
    results = dedupe_images(**test_data)
    assert results == []
    mock_deepface.verify.assert_not_called()


@pytest.mark.django_db
def test_dedupe_images_with_facial_error(mock_deepface, sample_data):
    """Test that files with facial errors are reported correctly."""
    test_data = copy.deepcopy(sample_data)
    test_data["encodings"]["file1.jpg"] = Image.StatusCode.NO_FACE_DETECTED.value
    results = dedupe_images(**test_data)
    expected = [("file1.jpg", "", 0, Image.StatusCode.NO_FACE_DETECTED.value)]
    assert results == expected
    mock_deepface.verify.assert_not_called()


@pytest.mark.django_db
def test_dedupe_images_progress_callback(mock_deepface, sample_data):
    """Test that the progress callback is called for each file."""
    mock_deepface.verify.return_value = {"distance": 0.2}
    progress_mock = Mock()
    sample_data["progress"] = progress_mock

    dedupe_images(**sample_data)
    assert progress_mock.call_count == len(sample_data["files0"])


@pytest.mark.django_db
def test_dedupe_images_complex_scenario(mock_deepface, complex_deduplication_data):
    """Test dedupe_images with a mix of duplicates, non-duplicates, errors, and ignored pairs."""
    mock_deepface.verify.side_effect = [
        {"distance": 0.01},  # f1-f2
        {"distance": 0.5},  # f1-f3
        # f1-f4 skipped because of no face detected in f4
        # f1-f5 in ignored pairs
        # f2-f3 skipped because f2 is in findings already
        # f2-f4 skipped because of no face detected in f4
        # f2-f5 skipped because f2 is in findings already
        # f3-f4 skipped because of no face detected in f4
        {"distance": 0.5},  # f3-f5
        # f4-f5 skipped because of no face detected in f4
    ]

    results = dedupe_images(**complex_deduplication_data)

    expected_findings = [
        ("f4.jpg", "", 0, Image.StatusCode.NO_FACE_DETECTED.value),
        ("f1.jpg", "f2.jpg", 0.99, Image.StatusCode.DEDUPLICATE_SUCCESS.value),
    ]

    # The order of findings might not be guaranteed
    assert len(results) == len(expected_findings)
    # Convert to set of tuples for order-agnostic comparison
    assert {tuple(item) for item in results} == {tuple(item) for item in expected_findings}
    # check all all expected calls were made
    with pytest.raises(StopIteration):
        mock_deepface.verify()

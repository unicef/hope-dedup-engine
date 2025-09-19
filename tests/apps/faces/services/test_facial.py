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
    """Fixture to mock the get_storage_manager function."""
    mock_get_storage = mocker.patch("hope_dedup_engine.apps.faces.services.facial.get_storage_manager")
    storage_mock = mock_get_storage.return_value
    storage_mock.load_image.return_value = "image_data"
    return storage_mock


@pytest.fixture
def sample_data():
    """Provide sample data for deduplication tests."""
    return {
        "files": ["file1.jpg", "file2.jpg"],
        "encodings": {"file1.jpg": [1.0], "file2.jpg": [1.1]},
        "ignored_pairs": set(),
        "dedupe_threshold": 0.9,
    }


@pytest.mark.django_db
def test_encode_faces_success(mock_deepface, mock_storage):
    """Test successful encoding of faces for a list of files."""
    files = ["file1.jpg", "file2.jpg"]
    mock_deepface.represent.side_effect = [[{"embedding": [1.0]}], [{"embedding": [2.0]}]]

    encoded, newly_encoded, added, existing = encode_faces(files)

    assert added == 2
    assert existing == 0
    assert newly_encoded == files
    assert encoded == {"file1.jpg": [1.0], "file2.jpg": [2.0]}
    assert mock_deepface.represent.call_count == 2


@pytest.mark.django_db
def test_encode_faces_with_pre_encodings(mock_deepface, mock_storage):
    """Test that files with pre-existing encodings are not re-encoded."""
    files = ["file1.jpg", "file2.jpg"]
    pre_encodings = {"file1.jpg": [1.0]}
    mock_deepface.represent.return_value = [{"embedding": [2.0]}]

    encoded, newly_encoded, added, existing = encode_faces(files, pre_encodings=pre_encodings)

    assert added == 1
    assert existing == 1
    assert newly_encoded == ["file2.jpg"]
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

    encoded, _, _, _ = encode_faces(files)
    assert encoded["file1.jpg"] == expected_status.name


@pytest.mark.django_db
def test_encode_faces_file_not_found(mock_deepface, mock_storage):
    """Test handling of ResourceNotFoundError from storage."""
    files = ["file1.jpg"]
    mock_storage.load_image.side_effect = ResourceNotFoundError("File not found")

    encoded, _, _, _ = encode_faces(files)
    assert encoded["file1.jpg"] == Image.StatusCode.NO_FILE_FOUND.name
    mock_deepface.represent.assert_not_called()


@pytest.mark.django_db
def test_dedupe_images_similarity_threshold():
    """Test dedupe_images with different similarity scores."""
    encodings = {
        "file1.jpg": [1.0, 0.0],  # vector for file1
        "file2.jpg": [0.9, 0.1],  # very similar to file1
        "file3.jpg": [0.0, 1.0],  # very different from file1
    }
    results = dedupe_images(encodings, encodings, ignored_pairs=set(), dedupe_threshold=0.9)
    assert len(results) == 1
    assert results[0][:2] == ("file1.jpg", "file2.jpg")
    assert results[0][2] == pytest.approx(0.994, abs=1e-3)

    results = dedupe_images(encodings, encodings, ignored_pairs=set(), dedupe_threshold=0.995)
    assert results == []


@pytest.mark.django_db
def test_dedupe_images_with_ignored_pair(sample_data):
    """Test that ignored pairs are not compared."""
    encodings = sample_data["encodings"]
    ignored = {("file1.jpg", "file2.jpg")}
    results = dedupe_images(encodings, encodings, ignored_pairs=ignored, dedupe_threshold=0.9)
    assert results == []


@pytest.mark.django_db
def test_dedupe_images_with_facial_error(sample_data):
    """Test that files with facial errors are reported correctly."""
    encodings = sample_data["encodings"]
    encodings["file1.jpg"] = Image.StatusCode.NO_FACE_DETECTED.name
    results = dedupe_images(encodings, encodings, ignored_pairs=set(), dedupe_threshold=0.9)
    expected = [("file1.jpg", "", 0, Image.StatusCode.NO_FACE_DETECTED.value)]
    assert results == expected


@pytest.mark.django_db
def test_dedupe_images_progress_callback(sample_data):
    """Test that the progress callback is called for each file."""
    progress_mock = Mock()
    encodings = sample_data["encodings"]
    dedupe_images(
        encodings,
        encodings,
        ignored_pairs=set(),
        dedupe_threshold=0.9,
        progress=progress_mock,
    )
    assert progress_mock.call_count == len(encodings)


@pytest.mark.django_db
def test_dedupe_images_complex_scenario():
    """Test dedupe_images with a mix of duplicates, non-duplicates, errors, and ignored pairs."""
    encodings = {
        "f1.jpg": [1.0, 0.0],  # a
        "f2.jpg": [0.9, 0.1],  # similar to a
        "f3.jpg": [0.0, 1.0],  # b
        "f4.jpg": Image.StatusCode.NO_FACE_DETECTED.name,  # error
        "f5.jpg": [0.8, 0.2],  # also similar to a
        "f6.jpg": [0.85, 0.15],  # also similar to a, and to f5. and ignored with f5
    }
    ignored = {("f5.jpg", "f6.jpg")}
    dedupe_threshold = 0.9

    results = dedupe_images(encodings, encodings, ignored, dedupe_threshold)

    # Expected findings:
    # f4 -> error finding
    # f1 -> f2 (sim ~0.99)
    # f1 -> f5 (sim ~0.98)
    # f1 -> f6 (sim ~0.99)
    # f2 -> f5 (sim ~0.99)
    # f2 -> f6 (sim ~1.0)
    # f5 -> f6 (ignored)
    expected_pairs = {
        ("f1.jpg", "f2.jpg"),
        ("f1.jpg", "f5.jpg"),
        ("f1.jpg", "f6.jpg"),
        ("f2.jpg", "f5.jpg"),
        ("f2.jpg", "f6.jpg"),
    }
    error_finding_found = False
    found_pairs = set()

    for finding in results:
        if finding[0] == "f4.jpg":
            assert finding[3] == Image.StatusCode.NO_FACE_DETECTED.value
            error_finding_found = True
        else:
            assert finding[3] == Image.StatusCode.DEDUPLICATE_SUCCESS.value
            found_pairs.add(tuple(sorted((finding[0], finding[1]))))

    assert error_finding_found
    assert found_pairs == expected_pairs

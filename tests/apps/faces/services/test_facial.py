import copy

import pytest
from azure.core.exceptions import ResourceNotFoundError

from hope_dedup_engine.apps.api.models import Image
from hope_dedup_engine.apps.faces.services.facial import (
    dedupe_images,
    encode_faces,
)


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
        "config": {
            "deduplicate": {},
            "face_confidence_threshold": 0.9,
            "duplicate_confidence_threshold": 60.0,
        },
    }


@pytest.mark.django_db
def test_encode_faces_success(mock_deepface, mock_storage):
    """Test successful encoding of faces for a list of files."""
    files = ["file1.jpg", "file2.jpg"]
    mock_deepface.represent.side_effect = [
        [{"embedding": [1.0], "face_confidence": 0.1}],
        [{"embedding": [2.0], "face_confidence": 0.1}],
    ]

    encoded, added, existing = encode_faces(files, process_encoding_error=lambda *_: None)

    assert added == 2
    assert existing == 0  # Based on hardcoded value in function
    assert encoded == {"file1.jpg": [1.0], "file2.jpg": [2.0]}
    assert mock_deepface.represent.call_count == 2


@pytest.mark.django_db
def test_encode_faces_with_pre_encodings(mock_deepface, mock_storage):
    """Test that files with pre-existing encodings are not re-encoded."""
    files = ["file1.jpg", "file2.jpg"]
    pre_encodings = {"file1.jpg": [1.0]}
    mock_deepface.represent.return_value = [{"embedding": [2.0], "face_confidence": 0.5}]

    encoded, added, existing = encode_faces(files, pre_encodings=pre_encodings, process_encoding_error={}.__setitem__)

    assert added == 1
    assert existing == 1
    assert encoded == {"file1.jpg": [1.0], "file2.jpg": [2.0]}
    mock_deepface.represent.assert_called_once_with("image_data")


@pytest.mark.parametrize(
    ("represent_kwargs", "expected_status"),
    [
        # 1) Multiple faces
        (
            {
                "return_value": [
                    {"embedding": [1.0], "face_confidence": 0.5},
                    {"embedding": [2.0], "face_confidence": 0.5},
                ]
            },
            Image.StatusCode.MULTIPLE_FACES_DETECTED,
        ),
        # 2) generic error
        ({"side_effect": TypeError("generic error")}, Image.StatusCode.GENERIC_ERROR),
        # 3) no face — through face_confidence == 0.0
        (
            {
                "return_value": [
                    {"embedding": [1.0], "face_confidence": 0.0},
                ]
            },
            Image.StatusCode.NO_FACE_DETECTED,
        ),
        # 4) weak face — NO_FACE_ACCEPTED (fc > 0, but below threshold)
        (
            {
                "return_value": [
                    {"embedding": [1.0], "face_confidence": 0.3},
                ]
            },
            Image.StatusCode.NO_FACE_ACCEPTED,
        ),
    ],
)
@pytest.mark.django_db
def test_encode_faces_deepface_outcomes(mock_deepface, mock_storage, represent_kwargs, expected_status):
    """Test handling of various outcomes from DeepFace.represent."""
    files = ["file1.jpg"]
    mock_deepface.represent.configure_mock(**represent_kwargs)
    config = {"encoding": {}, "face_confidence_threshold": 0.9}

    encoded, _, _ = encode_faces(files, process_encoding_error={}.__setitem__, config=config)

    assert encoded["file1.jpg"] == expected_status.value


@pytest.mark.django_db
def test_encode_faces_file_not_found(mock_deepface, mock_storage):
    """Test handling of ResourceNotFoundError from storage."""
    files = ["file1.jpg"]
    mock_storage.load_image.side_effect = ResourceNotFoundError("File not found")

    encoded, _, _ = encode_faces(files, process_encoding_error={}.__setitem__)
    assert encoded["file1.jpg"] == Image.StatusCode.NO_FILE_FOUND.value
    mock_deepface.represent.assert_not_called()


@pytest.mark.django_db
@pytest.mark.parametrize(
    ("verify_return", "expected_result"),
    [
        (
            {"confidence": 70.0},
            [("file1.jpg", "file2.jpg", 0.7, Image.StatusCode.DEDUPLICATE_SUCCESS.value)],
        ),
        ({"confidence": 50.0}, []),
    ],
)
def test_dedupe_images_confidence_threshold(mock_deepface, sample_data, verify_return, expected_result):
    """Test dedupe_images with different confidence scores."""
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
def test_dedupe_images_complex_scenario(mock_deepface, complex_deduplication_data):
    """Test dedupe_images with a mix of duplicates, non-duplicates, errors, and ignored pairs."""
    mock_deepface.verify.side_effect = [
        {"confidence": 99.0},  # f1-f2
        {"confidence": 50.0},  # f1-f3
        # f1-f4 skipped because of no face detected in f4
        # f1-f5 in ignored pairs
        {"confidence": 50.0},  # f2-f3
        # f2-f4 skipped because of no face detected in f4
        {"confidence": 50.0},  # f2-f5
        # f3-f4 skipped because of no face detected in f4
        {"confidence": 50.0},  # f3-f5
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

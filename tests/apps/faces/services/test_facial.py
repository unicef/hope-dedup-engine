import copy

import pytest
from azure.core.exceptions import ResourceNotFoundError

from hope_dedup_engine.apps.api.models import Encoding
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
def sample_data(deduplication_set_factory, encoding_factory):
    """Provide sample data for deduplication tests."""
    deduplication_set = deduplication_set_factory()
    return {
        "deduplication_set": deduplication_set,
        "encodings0": [encoding_factory(deduplication_set=deduplication_set, filename="file1.jpg", embedding=[1.0])],
        "encodings1": [encoding_factory(deduplication_set=deduplication_set, filename="file2.jpg", embedding=[1.1])],
        "ignored_pairs": set(),
        "duplicate_confidence_threshold": 60.0,
        "model_name": "model",
        "detector_backend": "backend",
        "distance_metric": "metric",
        "align": True,
        "silent": True,
    }


@pytest.mark.django_db
def test_encode_faces_success(mock_deepface, mock_storage, deduplication_set_factory, encoding_factory):
    """Test successful encoding of faces for a list of files."""
    deduplication_set = deduplication_set_factory()
    encoding0 = encoding_factory(deduplication_set=deduplication_set, filename="file1.jpg", embedding=None)
    encoding1 = encoding_factory(deduplication_set=deduplication_set, filename="file2.jpg", embedding=None)
    mock_deepface.represent.side_effect = [
        [{"embedding": [1.0], "face_confidence": 0.1}],
        [{"embedding": [2.0], "face_confidence": 0.1}],
    ]

    encode_faces(deduplication_set, [encoding0.id, encoding1.id], 0.1, "model", "backend", True)

    encoding0.refresh_from_db()
    encoding1.refresh_from_db()
    assert encoding0.embedding == [1.0]
    assert encoding1.embedding == [2.0]
    assert mock_deepface.represent.call_count == 2


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
            Encoding.StatusCode.MULTIPLE_FACES_DETECTED,
        ),
        # 2) generic error
        ({"side_effect": TypeError("generic error")}, Encoding.StatusCode.GENERIC_ERROR),
        # 3) no face — through face_confidence == 0.0
        (
            {
                "return_value": [
                    {"embedding": [1.0], "face_confidence": 0.0},
                ]
            },
            Encoding.StatusCode.NO_FACE_DETECTED,
        ),
        # 4) weak face — NO_FACE_ACCEPTED (fc > 0, but below threshold)
        (
            {
                "return_value": [
                    {"embedding": [1.0], "face_confidence": 0.3},
                ]
            },
            Encoding.StatusCode.FACE_NOT_ACCEPTED,
        ),
    ],
)
@pytest.mark.django_db
def test_encode_faces_deepface_outcomes(
    mock_deepface, mock_storage, encoding_factory, represent_kwargs, expected_status
):
    """Test handling of various outcomes from DeepFace.represent."""
    encoding = encoding_factory(filename="file1.jpg", embedding=None)
    mock_deepface.represent.configure_mock(**represent_kwargs)

    encode_faces(encoding.deduplication_set, [encoding.id], 0.9, "model", "backend", True)

    encoding.refresh_from_db()
    assert encoding.embedding_status_code == expected_status.value


@pytest.mark.django_db
def test_encode_faces_file_not_found(mock_deepface, mock_storage, encoding_factory):
    """Test handling of ResourceNotFoundError from storage."""
    encoding = encoding_factory(filename="file1.jpg", embedding=None)
    mock_storage.load_image.side_effect = ResourceNotFoundError("File not found")

    encode_faces(encoding.deduplication_set, [encoding.id], 0.9, "model", "backend", True)

    encoding.refresh_from_db()
    assert encoding.embedding_status_code == Encoding.StatusCode.FILE_NOT_FOUND.value
    mock_deepface.represent.assert_not_called()


@pytest.mark.django_db
@pytest.mark.parametrize(
    ("verify_return", "expected_result"),
    [
        (
            {"confidence": 70.0},
            [("file1.jpg", "file2.jpg", 0.7, Encoding.StatusCode.DEDUPLICATE_SUCCESS.value)],
        ),
        ({"confidence": 50.0}, []),
    ],
)
def test_dedupe_images_confidence_threshold(mock_deepface, sample_data, verify_return, expected_result):
    """Test dedupe_images with different confidence scores."""
    mock_deepface.verify.return_value = verify_return

    dedupe_images(**sample_data)

    if expected_result:
        pass
    else:
        assert sample_data["deduplication_set"].finding_set.count() == 0
    mock_deepface.verify.assert_called_once_with(
        sample_data["encodings0"][0].embedding,
        sample_data["encodings1"][0].embedding,
        model_name="model",
        detector_backend="backend",
        distance_metric="metric",
        align=True,
        silent=True,
    )


@pytest.mark.django_db
def test_dedupe_images_with_ignored_pair(mock_deepface, sample_data):
    """Test that ignored pairs are not compared."""
    test_data = copy.deepcopy(sample_data)
    test_data["ignored_pairs"] = {frozenset(("file1.jpg", "file2.jpg"))}
    dedupe_images(**test_data)
    assert sample_data["deduplication_set"].finding_set.count() == 0
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

    dedupe_images(**complex_deduplication_data)
    assert complex_deduplication_data["deduplication_set"].finding_set.count() == 1
    finding = complex_deduplication_data["deduplication_set"].finding_set.first()
    assert finding.first_filename == "f1.jpg"
    assert finding.second_filename == "f2.jpg"
    assert finding.score == 0.99
    assert finding.status_code == Encoding.StatusCode.DEDUPLICATE_SUCCESS.value

    with pytest.raises(StopIteration):
        mock_deepface.verify()

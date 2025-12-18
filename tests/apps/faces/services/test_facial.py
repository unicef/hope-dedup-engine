import copy

import numpy as np
import pytest
from azure.core.exceptions import ResourceNotFoundError

from hope_dedup_engine.apps.api.models import Encoding
from hope_dedup_engine.apps.faces.services.facial import (
    dedupe_images,
    encode_face,
    encode_faces,
    face_coverage_ratio,
)

MODEL_NAME = "model"
DETECTOR_BACKEND = "backend"
ALIGN = True
IMG_SIDE = 300


def fa(*, w: int, h: int, x: int = 0, y: int = 0) -> dict[str, int]:
    return {"x": x, "y": y, "w": w, "h": h}


def cov(*, w: int, h: int, side: int = IMG_SIDE) -> float:
    return round((w * h) / (side * side), 4)


def assert_findings(ds, expected: list[tuple[str, str, float, str]]) -> None:
    """Assert DeduplicationSet.finding_set contains exactly the expected findings."""
    assert ds.finding_set.count() == len(expected)
    for f0, f1, score, status_code in expected:
        finding = ds.finding_set.get(first_encoding__filename=f0, second_encoding__filename=f1)
        assert finding.score == pytest.approx(score)
        assert finding.status_code == status_code


@pytest.fixture
def mock_deepface(mocker):
    """Fixture to mock the DeepFace module used by the facial service."""
    return mocker.patch("hope_dedup_engine.apps.faces.services.facial.DeepFace")


@pytest.fixture
def sample_image() -> np.ndarray:
    """Sample image data for face encoding tests."""
    return np.zeros((IMG_SIDE, IMG_SIDE, 3), dtype=np.uint8)


@pytest.fixture
def mock_storage(mocker, sample_image):
    """Fixture to mock ImagesStorageManager and return a numpy image by default."""
    storage_mock = mocker.patch("hope_dedup_engine.apps.faces.services.facial.ImagesStorageManager").return_value
    storage_mock.load_image.return_value = sample_image
    return storage_mock


@pytest.fixture
def call_encode_face(mock_deepface, sample_image):
    """Call encode_face with a configurable DeepFace.represent return value."""

    def _call(represent_return, *, fc_th: float = 0.1, cov_th: float = 0.0):
        mock_deepface.represent.return_value = represent_return
        return encode_face(
            sample_image,
            face_confidence_threshold=fc_th,
            face_coverage_threshold=cov_th,
            model_name=MODEL_NAME,
            detector_backend=DETECTOR_BACKEND,
            align=ALIGN,
        )

    return _call


@pytest.fixture
def sample_data(deduplication_set_factory, encoding_factory):
    """Provide sample data for dedupe_images tests."""
    deduplication_set = deduplication_set_factory()
    return {
        "deduplication_set": deduplication_set,
        "encodings0": [encoding_factory(deduplication_set=deduplication_set, filename="file1.jpg", embedding=[1.0])],
        "encodings1": [encoding_factory(deduplication_set=deduplication_set, filename="file2.jpg", embedding=[1.1])],
        "ignored_pairs": set(),
        "duplicate_confidence_threshold": 60.0,
        "model_name": MODEL_NAME,
        "detector_backend": DETECTOR_BACKEND,
        "distance_metric": "metric",
        "align": ALIGN,
        "silent": True,
    }


# --- face_coverage_ratio -------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("fa_", "img_w", "img_h", "expected"),
    [
        ({"w": 10, "h": 10}, 100, 100, 0.01),
        ({"w": 0, "h": 10}, 100, 100, 0.0),
        ({"w": 10, "h": 10}, 0, 100, 0.0),
    ],
    ids=["normal_case", "zero_width_face", "zero_image_width"],
)
def test_face_coverage_ratio(fa_, img_w, img_h, expected):
    """Test face_coverage_ratio computes bbox/image area ratio."""
    assert face_coverage_ratio(fa=fa_, img_w=img_w, img_h=img_h) == pytest.approx(expected)


# --- encode_face ----------------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("represent_return", "fc_th", "cov_th", "exp_embedding", "exp_status", "exp_coverage"),
    [
        ([], 0.1, 0.0, None, Encoding.StatusCode.NO_FACE_DETECTED, None),
        (None, 0.1, 0.0, None, Encoding.StatusCode.GENERIC_ERROR, None),
        (
            [{"embedding": [1.0], "face_confidence": 0.0, "facial_area": fa(w=10, h=10)}],
            0.1,
            0.0,
            None,
            Encoding.StatusCode.NO_FACE_DETECTED,
            None,
        ),
        (
            [{"embedding": [1.0], "face_confidence": 0.05, "facial_area": fa(w=10, h=10)}],
            0.1,
            0.0,
            None,
            Encoding.StatusCode.FACE_NOT_ACCEPTED,
            None,
        ),
        ([{"embedding": [1.0], "face_confidence": 0.99}], 0.1, 0.0, None, Encoding.StatusCode.GENERIC_ERROR, None),
        (
            [{"embedding": [1.0], "face_confidence": 0.99, "facial_area": fa(w=10, h=10)}],
            0.1,
            0.05,
            None,
            Encoding.StatusCode.INSUFFICIENT_FACE_COVERAGE,
            cov(w=10, h=10),
        ),
        (
            [{"embedding": [1.0], "face_confidence": 0.99, "facial_area": fa(w=120, h=170)}],
            0.1,
            0.0,
            [1.0],
            None,
            pytest.approx(cov(w=120, h=170)),
        ),
    ],
    ids=[
        "no_face_detected",
        "generic_error",
        "no_face_detected_zero_confidence",
        "face_not_accepted",
        "generic_error_no_facial_area",
        "insufficient_face_coverage",
        "successful_encoding",
    ],
)
def test_encode_face_outcomes(
    call_encode_face, represent_return, fc_th, cov_th, exp_embedding, exp_status, exp_coverage
):
    """Test encode_face status/coverage outcomes across represent shapes and thresholds."""
    embedding, status, coverage = call_encode_face(represent_return, fc_th=fc_th, cov_th=cov_th)
    assert embedding == exp_embedding
    assert status == exp_status
    assert coverage == exp_coverage


# --- encode_faces ----------------------------------------------------------------------------------


@pytest.mark.django_db
def test_encode_faces_success(mock_deepface, mock_storage, deduplication_set_factory, encoding_factory):
    """Test successful encoding of faces for a list of files."""
    deduplication_set = deduplication_set_factory()
    encoding0 = encoding_factory(deduplication_set=deduplication_set, filename="file1.jpg", embedding=None)
    encoding1 = encoding_factory(deduplication_set=deduplication_set, filename="file2.jpg", embedding=None)

    mock_deepface.represent.side_effect = [
        [{"embedding": [1.0], "face_confidence": 0.1, "facial_area": fa(w=120, h=170)}],
        [{"embedding": [2.0], "face_confidence": 0.1, "facial_area": fa(w=120, h=170)}],
    ]

    encode_faces(deduplication_set, [encoding0.id, encoding1.id], 0.1, 0.0, MODEL_NAME, DETECTOR_BACKEND, ALIGN)

    encoding0.refresh_from_db()
    encoding1.refresh_from_db()
    assert encoding0.embedding == [1.0]
    assert encoding1.embedding == [2.0]
    assert mock_deepface.represent.call_count == 2


@pytest.mark.parametrize(
    ("represent_kwargs", "coverage_th", "expected_status"),
    [
        (
            {
                "return_value": [
                    {"embedding": [1.0], "face_confidence": 0.5},
                    {"embedding": [2.0], "face_confidence": 0.5},
                ]
            },
            0.0,
            Encoding.StatusCode.MULTIPLE_FACES_DETECTED,
        ),
        ({"side_effect": TypeError("generic error")}, 0.0, Encoding.StatusCode.GENERIC_ERROR),
        (
            {"return_value": [{"embedding": [1.0], "face_confidence": 0.0, "facial_area": fa(w=10, h=10)}]},
            0.0,
            Encoding.StatusCode.NO_FACE_DETECTED,
        ),
        (
            {"return_value": [{"embedding": [1.0], "face_confidence": 0.3, "facial_area": fa(w=10, h=10)}]},
            0.0,
            Encoding.StatusCode.FACE_NOT_ACCEPTED,
        ),
        ({"return_value": [{"embedding": [1.0], "face_confidence": 0.99}]}, 0.0, Encoding.StatusCode.GENERIC_ERROR),
        (
            {"return_value": [{"embedding": [1.0], "face_confidence": 0.99, "facial_area": fa(w=10, h=10)}]},
            0.05,
            Encoding.StatusCode.INSUFFICIENT_FACE_COVERAGE,
        ),
    ],
    ids=[
        "multiple_faces_detected",
        "generic_error",
        "no_face_detected",
        "face_not_accepted",
        "generic_error_no_facial_area",
        "insufficient_face_coverage",
    ],
)
@pytest.mark.django_db
def test_encode_faces_deepface_outcomes(
    mock_deepface, mock_storage, encoding_factory, represent_kwargs, coverage_th, expected_status
):
    """Test encode_faces persists status codes for represent outcomes."""
    encoding = encoding_factory(filename="file1.jpg", embedding=None)
    mock_deepface.represent.configure_mock(**represent_kwargs)

    encode_faces(encoding.deduplication_set, [encoding.id], 0.9, coverage_th, MODEL_NAME, DETECTOR_BACKEND, ALIGN)

    encoding.refresh_from_db()
    assert encoding.embedding_status_code == expected_status.value


@pytest.mark.django_db
def test_encode_faces_file_not_found(mock_deepface, mock_storage, encoding_factory):
    """Test handling of ResourceNotFoundError from storage."""
    encoding = encoding_factory(filename="file1.jpg", embedding=None)
    mock_storage.load_image.side_effect = ResourceNotFoundError("File not found")

    encode_faces(encoding.deduplication_set, [encoding.id], 0.9, 0.0, MODEL_NAME, DETECTOR_BACKEND, ALIGN)

    encoding.refresh_from_db()
    assert encoding.embedding_status_code == Encoding.StatusCode.FILE_NOT_FOUND.value
    mock_deepface.represent.assert_not_called()


# --- dedupe_images ----------------------------------------------------------------------------------


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
    ids=["above_threshold", "below_threshold"],
)
def test_dedupe_images_confidence_threshold(mock_deepface, sample_data, verify_return, expected_result):
    """Test dedupe_images creates findings only above the configured confidence threshold."""
    mock_deepface.verify.return_value = verify_return

    dedupe_images(**sample_data)

    assert_findings(sample_data["deduplication_set"], expected_result)
    mock_deepface.verify.assert_called_once_with(
        sample_data["encodings0"][0].embedding,
        sample_data["encodings1"][0].embedding,
        model_name=MODEL_NAME,
        detector_backend=DETECTOR_BACKEND,
        distance_metric=sample_data["distance_metric"],
        align=ALIGN,
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
    mock_deepface.verify.side_effect = [
        {"confidence": 99.0},  # f1-f2
        {"confidence": 50.0},  # f1-f3
        # f1-f4 skipped because of ignored_pairs
        {"confidence": 50.0},  # f2-f3
        {"confidence": 50.0},  # f2-f4
        {"confidence": 50.0},  # f3-f4
    ]

    dedupe_images(**complex_deduplication_data)

    dedup_set = complex_deduplication_data["deduplication_set"]
    assert dedup_set.finding_set.count() == 1
    finding = dedup_set.finding_set.first()
    assert finding.first_encoding.filename == "f1.jpg"
    assert finding.second_encoding.filename == "f2.jpg"
    assert finding.score == 0.99
    assert finding.status_code == Encoding.StatusCode.DEDUPLICATE_SUCCESS.value
    assert mock_deepface.verify.call_count == 5

from typing import cast, TYPE_CHECKING
from unittest.mock import Mock

import pytest
from pytest_mock import MockerFixture

from hope_dedup_engine.apps.api.admin.encoding.utils.process import deduplicate, detect_face, Detection, Finding
from hope_dedup_engine.apps.api.models import Encoding

if TYPE_CHECKING:
    from django.db.models import QuerySet

RECOGNITION_MODEL = "recognition_model"
DETECTOR_BACKEND = "detector_backend"
DISTANCE_METRIC = "distance_metric"
FACE_DETECTION_CONFIDENCE_THRESHOLD = 0.42

EMBEDDING = Mock()
VALID_CONFIDENCE = 0.52
VALID_CONFIDENCE_PERCENTS = VALID_CONFIDENCE * 100
ZERO_CONFIDENCE = 0.0
FACE_REPRESENTATION = {"face_confidence": VALID_CONFIDENCE, "embedding": EMBEDDING}
NO_FACE_REPRESENTATION = {"face_confidence": ZERO_CONFIDENCE, "embedding": EMBEDDING}

pytestmark = pytest.mark.override_config(
    DEFAULT_RECOGNITION_MODEL=RECOGNITION_MODEL,
    DEFAULT_DETECTOR_BACKEND=DETECTOR_BACKEND,
    DEFAULT_DISTANCE_METRIC=DISTANCE_METRIC,
    DEFAULT_FACE_DETECTION_CONFIDENCE_THRESHOLD=FACE_DETECTION_CONFIDENCE_THRESHOLD,
)


@pytest.fixture
def load_image_mock(mocker: MockerFixture) -> Mock:
    return mocker.patch(
        "hope_dedup_engine.apps.api.admin.encoding.utils.process.load_image",
        return_value=Mock(name="image-array"),
    )


@pytest.fixture
def deepface_class_mock(mocker: MockerFixture) -> Mock:
    return mocker.patch("hope_dedup_engine.apps.api.admin.encoding.utils.process.DeepFace")


@pytest.fixture
def detect_face_mock(mocker: MockerFixture) -> Mock:
    return mocker.patch("hope_dedup_engine.apps.api.admin.encoding.utils.process.detect_face")


def test_detect_face_no_face_found(encoding: Encoding, load_image_mock: Mock, deepface_class_mock: Mock) -> None:
    deepface_class_mock.represent.return_value = [NO_FACE_REPRESENTATION]
    assert detect_face(encoding) == Detection(encoding, ZERO_CONFIDENCE, EMBEDDING)


def test_detect_face_multiple_faces_found(encoding: Encoding, load_image_mock: Mock, deepface_class_mock: Mock) -> None:
    deepface_class_mock.represent.return_value = [FACE_REPRESENTATION, FACE_REPRESENTATION]
    assert detect_face(encoding) is None


def test_detect_face_single_face_found(encoding: Encoding, load_image_mock: Mock, deepface_class_mock: Mock) -> None:
    deepface_class_mock.represent.return_value = [FACE_REPRESENTATION]
    assert detect_face(encoding) == Detection(encoding, VALID_CONFIDENCE_PERCENTS, EMBEDDING)


def test_detect_face_represent_arguments(encoding: Encoding, load_image_mock: Mock, deepface_class_mock: Mock) -> None:
    detect_face(encoding)
    deepface_class_mock.represent.assert_called_once_with(
        load_image_mock.return_value,
        model_name=RECOGNITION_MODEL,
        detector_backend=DETECTOR_BACKEND,
        max_faces=2,
        enforce_detection=False,
    )


def test_detect_face_load_image_arguments(encoding: Encoding, load_image_mock: Mock) -> None:
    detect_face(encoding)
    load_image_mock.assert_called_once_with(encoding.filename)


def test_deduplicate_no_images(load_image_mock: Mock) -> None:
    assert deduplicate(cast("QuerySet[Encoding]", [])) == []


def test_deduplicate_no_faces_detected(encoding: Encoding, detect_face_mock: Mock) -> None:
    detect_face_mock.return_value = Detection(encoding, ZERO_CONFIDENCE, EMBEDDING)
    assert deduplicate(cast("QuerySet[Encoding]", [encoding, encoding])) == []


def test_deduplicate_faces_detected(encoding: Encoding, detect_face_mock: Mock, deepface_class_mock: Mock) -> None:
    detect_face_mock.return_value = Detection(encoding, VALID_CONFIDENCE_PERCENTS, EMBEDDING)
    expected_confidence = deepface_class_mock.verify.return_value.__getitem__.return_value
    assert deduplicate(cast("QuerySet[Encoding]", [encoding, encoding])) == [
        Finding(confidence=expected_confidence, encoding0=encoding, encoding1=encoding)
    ]

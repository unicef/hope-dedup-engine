from unittest.mock import MagicMock, patch

import numpy as np
import pytest

from hope_dedup_engine.apps.api.deduplication.config import DeduplicationSetConfig
from hope_dedup_engine.apps.faces.services.quality import (
    check_image_quality,
    compute_ofiq_scores,
    evaluate_quality_thresholds,
    get_active_thresholds,
)


def make_config(**overrides) -> DeduplicationSetConfig:
    defaults = {
        "sharpness_threshold": 0,
        "dynamic_range_threshold": 0,
        "no_head_cover_threshold": 0,
        "eyes_open_threshold": 0,
        "inter_eye_distance_threshold": 0,
        "unified_quality_score_threshold": 0,
    }
    defaults.update(overrides)
    return DeduplicationSetConfig(**defaults)


@pytest.mark.parametrize(
    ("config_kwargs", "expected"),
    [
        ({}, {}),
        ({"sharpness_threshold": 50}, {"Sharpness": 50}),
        (
            {"sharpness_threshold": 40, "eyes_open_threshold": 70},
            {"Sharpness": 40, "EyesOpen": 70},
        ),
        (
            {
                "sharpness_threshold": 10,
                "dynamic_range_threshold": 20,
                "no_head_cover_threshold": 30,
                "eyes_open_threshold": 40,
                "inter_eye_distance_threshold": 50,
                "unified_quality_score_threshold": 60,
            },
            {
                "Sharpness": 10,
                "DynamicRange": 20,
                "NoHeadCoverings": 30,
                "EyesOpen": 40,
                "InterEyeDistance": 50,
                "UnifiedQualityScore": 60,
            },
        ),
    ],
    ids=["all_zero", "single_threshold", "two_thresholds", "all_thresholds"],
)
def test_get_active_thresholds(config_kwargs, expected):
    config = make_config(**config_kwargs)
    assert get_active_thresholds(config) == expected


@pytest.fixture
def sample_bgr_image() -> np.ndarray:
    return np.zeros((100, 100, 3), dtype=np.uint8)


@pytest.fixture
def mock_ofiq():
    return MagicMock()


@patch("hope_dedup_engine.apps.faces.services.quality.cv2.cvtColor")
def test_compute_ofiq_scores_normalizes_to_0_1(mock_cvt, mock_ofiq, sample_bgr_image):
    mock_cvt.return_value = sample_bgr_image
    mock_ofiq.vector_quality.return_value = {"Sharpness": 80.0, "EyesOpen": 0.0}

    scores, face_detected = compute_ofiq_scores(mock_ofiq, sample_bgr_image)

    assert face_detected is True
    assert scores == {"Sharpness": 0.8, "EyesOpen": 0.0}


@patch("hope_dedup_engine.apps.faces.services.quality.cv2.cvtColor")
def test_compute_ofiq_scores_preserves_none_values(mock_cvt, mock_ofiq, sample_bgr_image):
    mock_cvt.return_value = sample_bgr_image
    mock_ofiq.vector_quality.return_value = {"Sharpness": 80.0, "EyesOpen": None}

    scores, face_detected = compute_ofiq_scores(mock_ofiq, sample_bgr_image)

    assert face_detected is True
    assert scores == {"Sharpness": 0.8, "EyesOpen": None}


@patch("hope_dedup_engine.apps.faces.services.quality.cv2.cvtColor")
def test_compute_ofiq_scores_no_face_returns_empty_dict(mock_cvt, mock_ofiq, sample_bgr_image):
    from ofiq import FaceDetectionError

    mock_cvt.return_value = sample_bgr_image
    mock_ofiq.vector_quality.side_effect = FaceDetectionError()

    scores, face_detected = compute_ofiq_scores(mock_ofiq, sample_bgr_image)

    assert face_detected is False
    assert scores == {}


@patch("hope_dedup_engine.apps.faces.services.quality.cv2.cvtColor")
def test_compute_ofiq_scores_converts_bgr_to_rgb(mock_cvt, mock_ofiq, sample_bgr_image):
    import cv2

    mock_cvt.return_value = sample_bgr_image
    mock_ofiq.vector_quality.return_value = {}

    compute_ofiq_scores(mock_ofiq, sample_bgr_image)

    mock_cvt.assert_called_once_with(sample_bgr_image, cv2.COLOR_BGR2RGB)


@pytest.mark.parametrize(
    ("scores", "thresholds", "expected"),
    [
        ({"Sharpness": 0.8}, {"Sharpness": 50}, True),
        ({"Sharpness": 0.3}, {"Sharpness": 50}, False),
        ({"Sharpness": 0.5}, {"Sharpness": 50}, True),
        ({"Sharpness": 0.8, "EyesOpen": 0.9}, {"Sharpness": 50, "EyesOpen": 70}, True),
        ({"Sharpness": 0.8, "EyesOpen": 0.5}, {"Sharpness": 50, "EyesOpen": 70}, False),
        ({}, {"Sharpness": 50}, False),
        ({"Sharpness": None}, {"Sharpness": 50}, False),
        ({"Sharpness": 0.8}, {}, True),
    ],
    ids=[
        "passes_threshold",
        "below_threshold",
        "exactly_at_threshold",
        "all_pass_multiple",
        "one_fails_multiple",
        "missing_metric",
        "none_score_value",
        "empty_thresholds",
    ],
)
def test_evaluate_quality_thresholds(scores, thresholds, expected):
    assert evaluate_quality_thresholds(scores, thresholds) == expected


@patch("hope_dedup_engine.apps.faces.services.quality.cv2.cvtColor")
def test_check_image_quality_passes(mock_cvt, mock_ofiq, sample_bgr_image):
    mock_cvt.return_value = sample_bgr_image
    mock_ofiq.vector_quality.return_value = {"Sharpness": 80.0, "EyesOpen": 90.0}

    result = check_image_quality(mock_ofiq, sample_bgr_image, {"Sharpness": 50, "EyesOpen": 70})

    assert result.passed is True
    assert result.face_detected is True
    assert result.scores == {"Sharpness": 0.8, "EyesOpen": 0.9}


@patch("hope_dedup_engine.apps.faces.services.quality.cv2.cvtColor")
def test_check_image_quality_fails_below_threshold(mock_cvt, mock_ofiq, sample_bgr_image):
    mock_cvt.return_value = sample_bgr_image
    mock_ofiq.vector_quality.return_value = {"Sharpness": 30.0, "EyesOpen": 90.0}

    result = check_image_quality(mock_ofiq, sample_bgr_image, {"Sharpness": 50, "EyesOpen": 70})

    assert result.passed is False
    assert result.face_detected is True


@patch("hope_dedup_engine.apps.faces.services.quality.cv2.cvtColor")
def test_check_image_quality_no_face_detected(mock_cvt, mock_ofiq, sample_bgr_image):
    from ofiq import FaceDetectionError

    mock_cvt.return_value = sample_bgr_image
    mock_ofiq.vector_quality.side_effect = FaceDetectionError()

    result = check_image_quality(mock_ofiq, sample_bgr_image, {"Sharpness": 50})

    assert result.passed is False
    assert result.face_detected is False


def test_check_image_quality_reuses_cached_scores(mock_ofiq):
    result = check_image_quality(mock_ofiq, None, {"Sharpness": 50}, cached_scores={"Sharpness": 0.8})

    assert result.passed is True
    assert result.face_detected is True
    assert result.scores == {"Sharpness": 0.8}
    mock_ofiq.vector_quality.assert_not_called()


def test_check_image_quality_cached_empty_scores_means_no_face(mock_ofiq):
    result = check_image_quality(mock_ofiq, None, {"Sharpness": 50}, cached_scores={})

    assert result.passed is False
    assert result.face_detected is False
    assert result.scores == {}
    mock_ofiq.vector_quality.assert_not_called()

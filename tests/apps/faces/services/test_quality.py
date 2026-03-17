from unittest.mock import MagicMock, patch

import numpy as np
import pytest

from hope_dedup_engine.apps.api.deduplication.config import DeduplicationSetConfig
from hope_dedup_engine.apps.faces.services.quality import (
    check_image_quality,
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
def test_check_image_quality_passes(mock_cvt, mock_ofiq, sample_bgr_image):
    mock_rgb = np.zeros((100, 100, 3), dtype=np.uint8)
    mock_cvt.return_value = mock_rgb
    mock_ofiq.vector_quality.return_value = {"Sharpness": 80.0, "EyesOpen": 90.0}

    result = check_image_quality(mock_ofiq, sample_bgr_image, {"Sharpness": 50, "EyesOpen": 70})

    assert result.passed is True
    assert result.face_detected is True
    assert result.failed_metrics == {}
    assert result.scores == {"Sharpness": 80.0, "EyesOpen": 90.0}


@patch("hope_dedup_engine.apps.faces.services.quality.cv2.cvtColor")
def test_check_image_quality_fails_below_threshold(mock_cvt, mock_ofiq, sample_bgr_image):
    mock_cvt.return_value = sample_bgr_image
    mock_ofiq.vector_quality.return_value = {"Sharpness": 30.0, "EyesOpen": 90.0}

    result = check_image_quality(mock_ofiq, sample_bgr_image, {"Sharpness": 50, "EyesOpen": 70})

    assert result.passed is False
    assert result.face_detected is True
    assert result.failed_metrics == {"Sharpness": 30.0}


@patch("hope_dedup_engine.apps.faces.services.quality.cv2.cvtColor")
def test_check_image_quality_missing_metric(mock_cvt, mock_ofiq, sample_bgr_image):
    mock_cvt.return_value = sample_bgr_image
    mock_ofiq.vector_quality.return_value = {}

    result = check_image_quality(mock_ofiq, sample_bgr_image, {"Sharpness": 50})

    assert result.passed is False
    assert result.failed_metrics == {"Sharpness": -1.0}


@patch("hope_dedup_engine.apps.faces.services.quality.cv2.cvtColor")
def test_check_image_quality_no_face_detected(mock_cvt, mock_ofiq, sample_bgr_image):
    from ofiq import FaceDetectionError

    mock_cvt.return_value = sample_bgr_image
    mock_ofiq.vector_quality.side_effect = FaceDetectionError()

    result = check_image_quality(mock_ofiq, sample_bgr_image, {"Sharpness": 50})

    assert result.passed is False
    assert result.face_detected is False


@patch("hope_dedup_engine.apps.faces.services.quality.cv2.cvtColor")
def test_check_image_quality_converts_bgr_to_rgb(mock_cvt, mock_ofiq, sample_bgr_image):
    import cv2

    mock_cvt.return_value = sample_bgr_image
    mock_ofiq.vector_quality.return_value = {}

    check_image_quality(mock_ofiq, sample_bgr_image, {})

    mock_cvt.assert_called_once_with(sample_bgr_image, cv2.COLOR_BGR2RGB)

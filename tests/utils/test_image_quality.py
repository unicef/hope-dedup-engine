import cv2
import numpy as np
import pytest
from constance.test import override_config

from hope_dedup_engine.apps.api.models import Encoding
from hope_dedup_engine.utils.image_quality import image_quality_result, michelson_contrast


@pytest.mark.parametrize(
    ("img", "expected"),
    [
        (np.zeros((2, 2, 3), dtype=np.uint8), 0.0),
        (np.array([[[0, 0, 0], [255, 255, 255]]], dtype=np.uint8), 1.0),
        (np.array([[[50, 50, 50], [100, 100, 100]]], dtype=np.uint8), (100.0 - 50.0) / (100.0 + 50.0)),
    ],
    ids=("denom_zero", "full_contrast_bw", "gray_levels"),
)
def test_michelson_contrast(img, expected) -> None:
    assert michelson_contrast(img) == pytest.approx(expected)


@override_config(DEFAULT_MICHELSON_CONTRAST_ENABLED=False, DEFAULT_MICHELSON_CONTRAST_THRESHOLD=0.5)
def test_image_quality_result_disabled(mocker) -> None:
    mc = mocker.patch("hope_dedup_engine.utils.image_quality.michelson_contrast")
    assert image_quality_result(np.zeros((2, 2, 3), dtype=np.uint8)) == (None, None)
    mc.assert_not_called()


@pytest.mark.parametrize(
    ("raw", "th", "exp_status", "exp_score"),
    [
        (0.9, 0.5, None, 0.9),
        (0.123456, 0.2, Encoding.StatusCode.IMAGE_QUALITY_TOO_LOW, 0.1235),
        (0.5, 0.5, None, 0.5),
    ],
    ids=("pass", "fail_rounded", "equal_pass"),
)
def test_image_quality_result_threshold_and_rounding(mocker, raw, th, exp_status, exp_score) -> None:
    with override_config(DEFAULT_MICHELSON_CONTRAST_ENABLED=True, DEFAULT_MICHELSON_CONTRAST_THRESHOLD=th):
        mocker.patch("hope_dedup_engine.utils.image_quality.michelson_contrast", return_value=raw)
        status, score = image_quality_result(np.zeros((2, 2, 3), dtype=np.uint8))
        assert status == exp_status
        assert score == exp_score


@pytest.mark.parametrize(
    "exc",
    [
        ValueError("bad"),
        TypeError("bad"),
        cv2.error(0, "fn", "bad", "file", 1),
    ],
    ids=("value_error", "type_error", "cv2_error"),
)
@override_config(DEFAULT_MICHELSON_CONTRAST_ENABLED=True, DEFAULT_MICHELSON_CONTRAST_THRESHOLD=0.5)
def test_image_quality_result_metric_error_is_non_fatal(mocker, exc) -> None:
    mocker.patch("hope_dedup_engine.utils.image_quality.michelson_contrast", side_effect=exc)
    assert image_quality_result(np.zeros((2, 2, 3), dtype=np.uint8)) == (None, None)

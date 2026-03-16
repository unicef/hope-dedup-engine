from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import TYPE_CHECKING
from ofiq import FaceDetectionError
from ofiq import OFIQ

import cv2

if TYPE_CHECKING:
    from numpy import ndarray
    from hope_dedup_engine.apps.api.deduplication.config import DeduplicationSetConfig

logger = logging.getLogger(__name__)

QUALITY_THRESHOLDS: dict[str, str] = {
    "sharpness_threshold": "Sharpness",
    "dynamic_range_threshold": "DynamicRange",
    "no_head_cover_threshold": "NoHeadCoverings",
    "eyes_open_threshold": "EyesOpen",
    "inter_eye_distance_threshold": "InterEyeDistance",
    "unified_quality_score_threshold": "UnifiedQualityScore",
}


@dataclass
class QualityCheckResult:
    passed: bool
    face_detected: bool = True
    scores: dict[str, float | None] = field(default_factory=dict)
    failed_metrics: dict[str, float] = field(default_factory=dict)


def get_active_thresholds(config: DeduplicationSetConfig) -> dict[str, float]:
    """Extract non-zero OFIQ thresholds from config, mapped to OFIQ metric names."""
    return {
        ofiq_name: threshold
        for config_key, ofiq_name in QUALITY_THRESHOLDS.items()
        if (threshold := getattr(config, config_key, 0)) > 0
    }


def check_image_quality(
    ofiq: OFIQ,
    image_bgr: ndarray,
    thresholds: dict[str, float],
) -> QualityCheckResult:
    """Run OFIQ quality assessment and check against thresholds."""
    image_rgb = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2RGB)

    try:
        scores = ofiq.vector_quality(image_rgb)
    except FaceDetectionError:
        return QualityCheckResult(passed=False, face_detected=False)

    failed = {}
    for metric_name, min_score in thresholds.items():
        actual = scores.get(metric_name)
        if actual is None or actual < min_score:
            failed[metric_name] = actual if actual is not None else -1.0

    return QualityCheckResult(
        passed=len(failed) == 0,
        scores=scores,
        failed_metrics=failed,
    )

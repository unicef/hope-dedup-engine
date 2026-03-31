from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import TYPE_CHECKING
from hope_dedup_engine.apps.api.deduplication.config import DeduplicationSetConfig
from ofiq import FaceDetectionError
from ofiq import OFIQ

import cv2

if TYPE_CHECKING:
    from numpy import ndarray


logger = logging.getLogger(__name__)


@dataclass
class QualityCheckResult:
    passed: bool
    face_detected: bool = True
    scores: dict[str, float | None] = field(default_factory=dict)


def get_active_thresholds(config: DeduplicationSetConfig) -> dict[str, float]:
    """Extract non-zero OFIQ thresholds from config, mapped to OFIQ metric names."""
    return {
        f.metadata["ofiq_metric"]: getattr(config, f.name)
        for f in DeduplicationSetConfig.setting_fields()
        if f.metadata.get("ofiq_metric") and getattr(config, f.name) > 0
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

    passed = all(
        (actual := scores.get(metric_name)) is not None and actual >= min_score
        for metric_name, min_score in thresholds.items()
    )

    return QualityCheckResult(
        passed=passed,
        scores={key: value / 100 if value else value for key, value in scores.items()},
    )

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from hope_dedup_engine.apps.api.deduplication.config import DeduplicationSetConfig
from ofiq import FaceDetectionError, OFIQ

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


def compute_ofiq_scores(
    ofiq: OFIQ,
    image_bgr: ndarray,
) -> tuple[dict[str, float | None], bool]:
    """Run OFIQ and return normalized 0-1 scores with face-detected flag.

    Returns ``({}, False)`` when OFIQ cannot find a face.
    """
    image_rgb = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2RGB)

    try:
        raw_scores = ofiq.vector_quality(image_rgb)
    except FaceDetectionError:
        return {}, False

    scores = {key: value / 100 if value is not None else value for key, value in raw_scores.items()}
    return scores, True


def evaluate_quality_thresholds(
    scores: dict[str, float | None],
    thresholds: dict[str, float],
) -> bool:
    """Compare cached 0-1 scores against 0-100 config thresholds.

    Returns ``True`` when all active thresholds pass or *thresholds* is empty.
    """
    if not thresholds:
        return True
    return all(
        (actual := scores.get(metric_name)) is not None and actual >= min_score / 100
        for metric_name, min_score in thresholds.items()
    )


def check_image_quality(
    ofiq: OFIQ,
    image_bgr: ndarray | None,
    thresholds: dict[str, float],
    cached_scores: dict[str, float | None] | None = None,
) -> QualityCheckResult:
    """Assess image quality, computing OFIQ scores or reusing cached ones.

    When *cached_scores* is provided it is reused as-is (an empty dict means a
    previous OFIQ run found no face); otherwise OFIQ runs on *image_bgr*.
    """
    if cached_scores is not None:
        scores, face_detected = cached_scores, bool(cached_scores)
    else:
        scores, face_detected = compute_ofiq_scores(ofiq, image_bgr)

    if not face_detected:
        return QualityCheckResult(passed=False, face_detected=False, scores=scores)

    passed = evaluate_quality_thresholds(scores, thresholds)
    return QualityCheckResult(passed=passed, scores=scores)

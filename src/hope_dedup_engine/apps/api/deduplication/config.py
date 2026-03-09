from dataclasses import dataclass, field
from typing import Any, Self
from uuid import UUID

from constance import config as constance_cfg

from hope_dedup_engine.apps.api.models import DeduplicationSet


def get_default_group_settings() -> dict[str, Any]:
    """Return a dict of current Constance defaults to snapshot into DeduplicationSetGroup.settings."""
    return {
        "recognition_model": constance_cfg.DEFAULT_RECOGNITION_MODEL,
        "detector_backend": constance_cfg.DEFAULT_DETECTOR_BACKEND,
        "distance_metric": constance_cfg.DEFAULT_DISTANCE_METRIC,
        "face_detection_confidence_threshold": constance_cfg.DEFAULT_FACE_DETECTION_CONFIDENCE_THRESHOLD,
        "face_coverage_threshold": constance_cfg.DEFAULT_FACE_COVERAGE_THRESHOLD,
        "duplicate_confidence_threshold": constance_cfg.DEFAULT_DUPLICATE_CONFIDENCE_THRESHOLD,
    }


SETTINGS_FIELDS = (
    "recognition_model",
    "detector_backend",
    "distance_metric",
    "face_detection_confidence_threshold",
    "face_coverage_threshold",
    "duplicate_confidence_threshold",
)


@dataclass
class DeduplicationSetConfig:
    deduplication_set_id: UUID | None = None
    recognition_model: str = field(default_factory=lambda: constance_cfg.DEFAULT_RECOGNITION_MODEL)
    detector_backend: str = field(default_factory=lambda: constance_cfg.DEFAULT_DETECTOR_BACKEND)
    distance_metric: str = field(default_factory=lambda: constance_cfg.DEFAULT_DISTANCE_METRIC)
    face_detection_confidence_threshold: float = field(
        default_factory=lambda: constance_cfg.DEFAULT_FACE_DETECTION_CONFIDENCE_THRESHOLD
    )
    face_coverage_threshold: float = field(default_factory=lambda: constance_cfg.DEFAULT_FACE_COVERAGE_THRESHOLD)
    duplicate_confidence_threshold: float = field(
        default_factory=lambda: constance_cfg.DEFAULT_DUPLICATE_CONFIDENCE_THRESHOLD * 100
    )  # Stored as 0-1 in settings, converted to 0-100 internally
    align: bool = True

    @classmethod
    def from_deduplication_set(cls, deduplication_set: DeduplicationSet) -> Self:
        settings = deduplication_set.group.settings or {}
        kwargs: dict[str, Any] = {"deduplication_set_id": deduplication_set.pk}
        for key in SETTINGS_FIELDS:
            if key in settings:
                value = settings[key]
                if key == "duplicate_confidence_threshold":
                    value = value * 100
                kwargs[key] = value
        return cls(**kwargs)

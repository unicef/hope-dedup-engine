import dataclasses
from dataclasses import dataclass, field
from typing import Any, Self
from uuid import UUID

from constance import config as constance_cfg

from hope_dedup_engine.apps.api.const import (
    DETECTOR_BACKEND_CHOICES,
    DISTANCE_METRIC_CHOICES,
    RECOGNITION_MODEL_CHOICES,
)
from hope_dedup_engine.apps.api.models import DeduplicationSet


def _meta(  # noqa
    *,
    category: str,
    help_text: str,
    admin: bool = True,
    api: bool = False,
    min_value: float | None = None,
    max_value: float | None = None,
    choices: tuple | None = None,
    ofiq_metric: str | None = None,
) -> dict[str, Any]:
    meta: dict[str, Any] = {
        "category": category,
        "help_text": help_text,
        "admin": admin,
        "api": api,
    }
    if choices is not None:
        meta["choices"] = choices
    else:
        meta["min_value"] = min_value if min_value is not None else 0.0
        meta["max_value"] = max_value if max_value is not None else 1.0
    if ofiq_metric:
        meta["ofiq_metric"] = ofiq_metric
    return meta


@dataclass
class DeduplicationSetConfig:
    deduplication_set_id: UUID | None = None

    recognition_model: str = field(
        default_factory=lambda: constance_cfg.DEFAULT_RECOGNITION_MODEL,
        metadata=_meta(
            category="recognition",
            choices=RECOGNITION_MODEL_CHOICES,
            help_text="Face recognition model for encoding face landmarks.",
        ),
    )
    detector_backend: str = field(
        default_factory=lambda: constance_cfg.DEFAULT_DETECTOR_BACKEND,
        metadata=_meta(
            category="detection",
            choices=DETECTOR_BACKEND_CHOICES,
            help_text="Face detector backend for detecting faces in images.",
        ),
    )
    distance_metric: str = field(
        default_factory=lambda: constance_cfg.DEFAULT_DISTANCE_METRIC,
        metadata=_meta(
            category="recognition",
            choices=DISTANCE_METRIC_CHOICES,
            help_text="Metric for measuring similarity between face embeddings.",
        ),
    )
    face_detection_confidence_threshold: float = field(
        default_factory=lambda: constance_cfg.DEFAULT_FACE_DETECTION_CONFIDENCE_THRESHOLD,
        metadata=_meta(
            category="detection",
            api=True,
            help_text="Minimum confidence score (0-1) for a detected face to be accepted.",
        ),
    )
    duplicate_confidence_threshold: float = field(
        default_factory=lambda: constance_cfg.DEFAULT_DUPLICATE_CONFIDENCE_THRESHOLD * 100,
        metadata=_meta(
            category="recognition",
            api=True,
            help_text="Threshold on face match confidence (0-1) for treating pairs as duplicates.",
        ),
    )
    sharpness_threshold: float = field(
        default_factory=lambda: constance_cfg.DEFAULT_SHARPNESS_THRESHOLD * 100,
        metadata=_meta(
            category="quality",
            api=True,
            ofiq_metric="Sharpness",
            help_text="Minimum sharpness score (0-1). 0 = disabled.",
        ),
    )
    dynamic_range_threshold: float = field(
        default_factory=lambda: constance_cfg.DEFAULT_DYNAMIC_RANGE_THRESHOLD * 100,
        metadata=_meta(
            category="quality",
            api=True,
            ofiq_metric="DynamicRange",
            help_text="Minimum dynamic range score (0-1). 0 = disabled.",
        ),
    )
    no_head_cover_threshold: float = field(
        default_factory=lambda: constance_cfg.DEFAULT_NO_HEAD_COVER_THRESHOLD * 100,
        metadata=_meta(
            category="quality",
            api=True,
            ofiq_metric="NoHeadCoverings",
            help_text="Minimum no-head-cover score (0-1). 0 = disabled.",
        ),
    )
    eyes_open_threshold: float = field(
        default_factory=lambda: constance_cfg.DEFAULT_EYES_OPEN_THRESHOLD * 100,
        metadata=_meta(
            category="quality",
            api=True,
            ofiq_metric="EyesOpen",
            help_text="Minimum eyes-open score (0-1). 0 = disabled.",
        ),
    )
    inter_eye_distance_threshold: float = field(
        default_factory=lambda: constance_cfg.DEFAULT_INTER_EYE_DISTANCE_THRESHOLD * 100,
        metadata=_meta(
            category="quality",
            api=True,
            ofiq_metric="InterEyeDistance",
            help_text="Minimum inter-eye distance score (0-1). 0 = disabled.",
        ),
    )
    unified_quality_score_threshold: float = field(
        default_factory=lambda: constance_cfg.DEFAULT_UNIFIED_QUALITY_SCORE_THRESHOLD * 100,
        metadata=_meta(
            category="quality",
            api=True,
            ofiq_metric="UnifiedQualityScore",
            help_text="Minimum unified quality score (0-1). 0 = disabled.",
        ),
    )

    align: bool = True

    def as_dict(self) -> dict[str, Any]:
        d = dataclasses.asdict(self)
        if isinstance(d.get("deduplication_set_id"), UUID):
            d["deduplication_set_id"] = str(d["deduplication_set_id"])
        return d

    @classmethod
    def setting_fields(cls, **filters: Any) -> list[dataclasses.Field]:
        """Return dataclass fields whose metadata matches all given key=value filters."""
        return [
            f for f in dataclasses.fields(cls) if f.metadata and all(f.metadata.get(k) == v for k, v in filters.items())
        ]

    @classmethod
    def from_deduplication_set(cls, deduplication_set: DeduplicationSet) -> Self:
        settings = deduplication_set.group.settings or {}
        kwargs: dict[str, Any] = {"deduplication_set_id": deduplication_set.pk}
        for f in cls.setting_fields():
            if f.name in settings:
                value = settings[f.name]
                if f.name == "duplicate_confidence_threshold" or f.metadata.get("ofiq_metric"):
                    value = value * 100
                kwargs[f.name] = value
        return cls(**kwargs)


def get_default_group_settings() -> dict[str, Any]:
    """Return a dict of current Constance defaults to snapshot into DeduplicationSetGroup.settings."""
    return {
        f.name: getattr(constance_cfg, f"DEFAULT_{f.name.upper()}") for f in DeduplicationSetConfig.setting_fields()
    }

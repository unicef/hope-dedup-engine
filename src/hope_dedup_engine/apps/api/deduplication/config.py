from dataclasses import dataclass, field
from typing import Any, Self
from uuid import UUID

from constance import config as constance_cfg

from hope_dedup_engine.apps.api.models import DeduplicationSet


@dataclass
class ModelOptions:
    model_name: str = field(default_factory=lambda: constance_cfg.FACE_RECOGNITION_MODEL)
    detector_backend: str = field(default_factory=lambda: constance_cfg.FACE_DETECTOR_BACKEND)

    def update(self, overrides: dict[str, Any]) -> None:
        for k, v in overrides.items():
            if hasattr(self, k):
                setattr(self, k, v)


@dataclass
class EncodingOptions(ModelOptions):
    pass


@dataclass
class DeduplicateOptions(ModelOptions):
    threshold: float = field(default_factory=lambda: constance_cfg.FACE_DISTANCE_THRESHOLD)
    silent: bool = True


@dataclass
class DeduplicationSetConfig:
    deduplication_set_id: UUID | None = None
    encoding: EncodingOptions = field(default_factory=EncodingOptions)
    deduplicate: DeduplicateOptions = field(default_factory=DeduplicateOptions)

    def update(self, overrides: dict[str, Any]) -> None:
        if not isinstance(overrides, dict):
            raise ValueError("Overrides values must be a dictionary.")
        for k, v in overrides.items():
            match k:
                case "encoding" if isinstance(v, dict):
                    self.encoding.update(v)
                case "deduplicate" if isinstance(v, dict):
                    self.deduplicate.update(v)
                case _ if hasattr(self, k):
                    setattr(self, k, v)
                case _:
                    raise KeyError(f"Unknown config key: {k}")

    @classmethod
    def from_deduplication_set(cls, deduplication_set: DeduplicationSet) -> Self:
        instance = cls(deduplication_set_id=deduplication_set.pk)
        if deduplication_set.config:
            instance.update(deduplication_set.config.settings)
        return instance

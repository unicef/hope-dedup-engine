from dataclasses import dataclass, field
from typing import Any, Self
from uuid import UUID

from django.db import models

from constance import config as constance_cfg

from hope_dedup_engine.apps.api.models.deduplication import DeduplicationSet
from hope_dedup_engine.apps.api.validators import validate_constance_config


class Config(models.Model):
    name = models.CharField(
        max_length=128, unique=True, null=True, blank=True, db_index=True
    )
    settings = models.JSONField(
        default=dict, null=True, blank=True, validators=[validate_constance_config]
    )

    def __str__(self) -> str:
        return self.name or f"ID: {self.pk}"

    def clean(self):

        super().clean()


@dataclass
class ModelOptions:
    model_name: str = field(default_factory=lambda: constance_cfg.MODEL_NAME)
    detector_backend: str = field(
        default_factory=lambda: constance_cfg.DETECTOR_BACKEND
    )

    def update(self, overrides: dict[str, Any]) -> None:
        for k, v in overrides.items():
            if hasattr(self, k):
                setattr(self, k, v)


@dataclass
class RepresentOptions(ModelOptions):
    pass


@dataclass
class VerifyOptions(ModelOptions):
    threshold: float = field(
        default_factory=lambda: constance_cfg.FACE_DISTANCE_THRESHOLD
    )
    silent: bool = True


@dataclass
class DeduplicationSetConfig:
    deduplication_set_id: UUID | None = None
    encoding: RepresentOptions = field(default_factory=RepresentOptions)
    deduplicate: VerifyOptions = field(default_factory=VerifyOptions)

    def update(self, overrides: dict[str, Any]) -> None:
        if not isinstance(overrides, dict):
            raise ValueError("Overrides values must be a dictionary.")
        for k, v in overrides.items():
            match k:
                case "model_name" | "detector_backend":
                    self.encoding.update({k: v})
                    self.deduplicate.update({k: v})
                case "face_distance_threshold":
                    self.deduplicate.update({"threshold": v})
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

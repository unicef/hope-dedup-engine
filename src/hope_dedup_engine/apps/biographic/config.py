import dataclasses
from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any, Self

from constance import config as constance_cfg

from hope_dedup_engine.apps.biographic.models import BiographicSet

CONSTANCE_PREFIX = "DEFAULT_BIOGRAPHIC_"


def _meta(*, kind: type, help_text: str, min_value: float = 0) -> dict[str, Any]:
    return {"kind": kind, "help_text": help_text, "min_value": min_value}


def _default(name: str) -> Any:
    return lambda: getattr(constance_cfg, f"{CONSTANCE_PREFIX}{name.upper()}")


@dataclass
class BiographicConfig:
    """Thresholds for one biographic run.

    Resolved per run as request override, then the group's settings, then the
    Constance default. The group's settings are a snapshot of Constance taken when
    the group was created, so Constance is only reached for a setting added since.
    """

    dataset_id: int | None = None

    duplicate_score: float = field(
        default_factory=_default("duplicate_score"),
        metadata=_meta(
            kind=float,
            help_text="Pairs scoring at or above this are duplicates. Also the Elasticsearch min_score.",
        ),
    )
    batch_duplicates_allowed: int = field(
        default_factory=_default("batch_duplicates_allowed"),
        metadata=_meta(kind=int, help_text="Abort when one record has more duplicates than this within its set."),
    )
    batch_duplicates_percentage: int = field(
        default_factory=_default("batch_duplicates_percentage"),
        metadata=_meta(
            kind=int, help_text="Abort when at least this percentage of the set has a duplicate in the set."
        ),
    )
    population_duplicates_allowed: int = field(
        default_factory=_default("population_duplicates_allowed"),
        metadata=_meta(kind=int, help_text="Abort when one record has more duplicates than this in the population."),
    )
    population_duplicates_percentage: int = field(
        default_factory=_default("population_duplicates_percentage"),
        metadata=_meta(
            kind=int, help_text="Abort when at least this percentage of the set has a duplicate in the population."
        ),
    )
    max_hits: int = field(
        default_factory=_default("max_hits"),
        metadata=_meta(kind=int, min_value=1, help_text="Maximum matches Elasticsearch returns per record."),
    )

    def as_dict(self) -> dict[str, Any]:
        return dataclasses.asdict(self)

    @classmethod
    def setting_fields(cls) -> list[dataclasses.Field]:
        return [f for f in dataclasses.fields(cls) if f.metadata]

    @classmethod
    def for_set(cls, dataset: BiographicSet, overrides: Mapping[str, Any] | None = None) -> Self:
        group_settings = dataset.group.settings or {}
        overrides = overrides or {}
        kwargs: dict[str, Any] = {"dataset_id": dataset.pk}
        for f in cls.setting_fields():
            if f.name in overrides:
                kwargs[f.name] = overrides[f.name]
            elif f.name in group_settings:
                kwargs[f.name] = group_settings[f.name]
        return cls(**kwargs)


def resolve_config(dataset: BiographicSet, overrides: Mapping[str, Any] | None = None) -> BiographicConfig:
    return BiographicConfig.for_set(dataset, overrides)


def get_default_group_settings() -> dict[str, Any]:
    """Return the current Constance defaults, to snapshot into a new `BiographicGroup.settings`."""
    return {f.name: _default(f.name)() for f in BiographicConfig.setting_fields()}

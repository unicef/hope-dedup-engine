import dataclasses
from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any, Final

from constance import config as constance_cfg

from hope_dedup_engine.apps.biographic.models import BiographicSet

_INT: Final[str] = "int"
_FLOAT: Final[str] = "float"


def _meta(kind: str, help_text: str) -> dict[str, Any]:
    return {"kind": kind, "help_text": help_text}


@dataclass
class BiographicConfig:
    """Duplicate threshold and abort limits for one biographic dataset.

    There is no possible-duplicate threshold. ``duplicate_score`` is also the
    Elasticsearch population ``min_score``.
    """

    dataset_id: int | None = None
    duplicate_score: float = field(
        default_factory=lambda: constance_cfg.DEFAULT_BIOGRAPHIC_DUPLICATE_SCORE,
        metadata=_meta(_FLOAT, "Duplicate threshold and Elasticsearch population min_score."),
    )
    batch_duplicates_allowed: int = field(
        default_factory=lambda: constance_cfg.DEFAULT_BIOGRAPHIC_BATCH_DUPLICATES_ALLOWED,
        metadata=_meta(_INT, "Abort threshold for batch hits per record."),
    )
    batch_duplicates_percentage: int = field(
        default_factory=lambda: constance_cfg.DEFAULT_BIOGRAPHIC_BATCH_DUPLICATES_PERCENTAGE,
        metadata=_meta(_INT, "Abort threshold for distinct batch duplicate share."),
    )
    population_duplicates_allowed: int = field(
        default_factory=lambda: constance_cfg.DEFAULT_BIOGRAPHIC_POPULATION_DUPLICATES_ALLOWED,
        metadata=_meta(_INT, "Abort threshold for population hits per record."),
    )
    population_duplicates_percentage: int = field(
        default_factory=lambda: constance_cfg.DEFAULT_BIOGRAPHIC_POPULATION_DUPLICATES_PERCENTAGE,
        metadata=_meta(_INT, "Abort threshold for distinct population duplicate share."),
    )
    max_hits: int = field(
        default_factory=lambda: constance_cfg.DEFAULT_BIOGRAPHIC_MAX_HITS,
        metadata=_meta(_INT, "Elasticsearch result size."),
    )

    @classmethod
    def setting_fields(cls) -> list[dataclasses.Field[Any]]:
        """Return settings that can be overridden. ``dataset_id`` is not a setting."""
        return [item for item in dataclasses.fields(cls) if item.metadata]


def _coerce(setting: dataclasses.Field[Any], value: Any) -> Any:
    if isinstance(value, bool) or not isinstance(value, int | float):
        raise ValueError(f"Invalid value for {setting.name}.")
    if setting.metadata["kind"] == _INT:
        return int(value)
    return float(value)


def resolve_config(dataset: BiographicSet, overrides: Mapping[str, Any] | None = None) -> BiographicConfig:
    """Resolve settings: request override, then group settings, then Constance."""
    group_settings = dataset.group.settings or {}
    request_overrides = {} if overrides is None else dict(overrides)
    settings = BiographicConfig.setting_fields()
    known = {item.name for item in settings}
    unknown = sorted(set(request_overrides) - known)
    if unknown:
        raise ValueError(f"Unknown biographic settings: {', '.join(unknown)}.")
    resolved: dict[str, Any] = {"dataset_id": dataset.pk}
    for setting in settings:
        if setting.name in request_overrides:
            resolved[setting.name] = _coerce(setting, request_overrides[setting.name])
        elif setting.name in group_settings:
            resolved[setting.name] = _coerce(setting, group_settings[setting.name])
    return BiographicConfig(**resolved)
